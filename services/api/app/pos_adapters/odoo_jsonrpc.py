"""Odoo JSON-RPC を用いた POS 連携アダプタ。

このモジュールは FastAPI 側から import される「差し替え可能な POS アダプタ」です。

対応内容
- アダプタ抽象（Protocol）
- Odoo Web JSON-RPC クライアント
  - /web/session/authenticate
  - /web/dataset/call_kw
- 受注（sale.order）
  - 下書き作成（sale.order.create）
  - 確定（sale.order.action_confirm）
- POS 注文（pos.order）
  - sync_from_ui（Odoo 19 系）

注意
- POS の sync_from_ui に渡す payload は Odoo バージョンや導入モジュールで変わります。
  実運用では POS 画面で注文した際の Network ペイロードを DevTools で確認し、
  build_pos_order_payload() を合わせるのが最短です。
- SKU は既定で product.product.default_code を使用します（cfg.sku_field で変更可能）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence
from uuid import uuid4

import httpx

# ============================================================
# アダプタ抽象（API 層から依存される境界）
# ============================================================


@dataclass(frozen=True)
class CheckoutLine:
    """チェックアウト明細の1行を表す入力モデル。"""

    # 商品を一意に識別するキー（default_code / barcode など）。
    sku: str
    # 購入数量。
    qty: float
    # 単価。None の場合は Odoo 側の既定価格計算に委譲する。
    price_unit: Optional[float] = None


@dataclass(frozen=True)
class CheckoutRequest:
    """API 層からアダプタ層へ渡すチェックアウト要求。"""

    # どの店舗からの要求かを識別するID。
    store_id: str
    # 操作者ID（任意）。
    operator_id: Optional[str]
    # 購入明細の配列。
    lines: list[CheckoutLine]
    # 伝票メモや補足情報（任意）。
    note: Optional[str] = None


@dataclass(frozen=True)
class CheckoutResult:
    """アダプタ層から API 層へ返す共通結果モデル。"""

    # 業務処理全体の成否。
    ok: bool
    # 作成対象モデル名（"sale.order" or "pos.order"）。
    target: str
    # 作成レコードID。取得不可な場合は None。
    record_id: Optional[int]
    # Odoo から返った生データ（調査用途）。
    raw: Any
    # エラー/補足メッセージ（任意）。
    message: Optional[str] = None


class PosAdapter(Protocol):
    """POS 連携の差し替えインターフェース。"""

    def checkout(self, req: CheckoutRequest) -> CheckoutResult:
        """チェックアウト要求を処理し、結果を返す。"""
        ...


# ============================================================
# Odoo JSON-RPC クライアント
# ============================================================


@dataclass(frozen=True)
class OdooConfig:
    """Odoo 連携に必要な設定値。"""

    # Odoo のベース URL（例: http://odoo:8069）。
    base_url: str  # 例: http://odoo:8069
    # Odoo データベース名。
    db: str
    # 認証ユーザー。
    username: str
    # 認証パスワード。
    password: str
    # HTTP タイムアウト秒。
    timeout_sec: float = 10.0

    # sale.order 用の既定値
    # 未指定時に使う顧客ID（店内客など）。
    default_partner_id: int = 1  # 例: 店内客（共通顧客）
    # 未指定時は Odoo 既定価格表に委譲。
    default_pricelist_id: Optional[int] = None

    # POS 用の既定値（sync_from_ui のみ）
    # mode="pos" でセッションID未指定時に使う値。
    default_pos_session_id: Optional[int] = None
    # sync_from_ui 呼び出し時に draft フラグへ反映する値。
    create_pos_draft: bool = True

    # SKU の参照フィールド（default_code / barcode など）
    # SKU と Odoo 商品を突合する際のキー列。
    sku_field: str = "default_code"


class OdooJsonRpcError(RuntimeError):
    """Odoo JSON-RPC からのエラーを表す例外。"""


class OdooJsonRpcClient:
    """Odoo Web(JSON-RPC) エンドポイントを叩く薄いラッパ。

    Note:
        - 認証後の cookie セッションを httpx.Client 内で維持する。
        - XML-RPC ではなく Web クライアント互換の JSON-RPC を利用する。
    """

    def __init__(self, cfg: OdooConfig) -> None:
        # 接続設定を保持する。
        self.cfg = cfg
        # keep-alive/cookie を再利用する HTTP クライアント。
        self._client = httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout_sec)
        # authenticate 後に確定する Odoo ユーザーID。
        self._uid: Optional[int] = None

    def close(self) -> None:
        """保持している HTTP コネクションをクローズする。"""
        self._client.close()

    def authenticate(self) -> int:
        """/web/session/authenticate で認証し、セッション cookie を確立する。"""
        # Odoo Web JSON-RPC の認証ペイロード。
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.cfg.db,
                "login": self.cfg.username,
                "password": self.cfg.password,
            },
            "id": 1,
        }
        # 認証 API 呼び出し。HTTP エラーは raise_for_status で例外化。
        res = self._client.post("/web/session/authenticate", json=payload)
        res.raise_for_status()
        # 返却 JSON 全体（error/result のどちらかを持つ）。
        data = res.json()

        # Odoo から明示エラーが返った場合は専用例外へ変換。
        if data.get("error"):
            raise OdooJsonRpcError(f"authenticate error: {data['error']}")

        # 成功時の result を取り出し、uid を取得する。
        result = data.get("result") or {}
        uid = result.get("uid")
        if not uid:
            raise OdooJsonRpcError(f"authenticate failed: {data}")

        # 以降の call_kw で利用できるよう保持する。
        self._uid = int(uid)
        return self._uid

    def call_kw(
        self,
        model: str,
        method: str,
        args: Sequence[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """/web/dataset/call_kw 経由で任意モデルメソッドを呼び出す。"""
        # 未認証なら先に認証し、セッションを確立する。
        if self._uid is None:
            self.authenticate()

        # Odoo Web JSON-RPC の標準 payload。
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": list(args or []),
                "kwargs": kwargs or {},
            },
            "id": 2,
        }
        # call_kw API 呼び出し。
        res = self._client.post("/web/dataset/call_kw", json=payload)
        res.raise_for_status()
        # 返却 JSON を解析する。
        data = res.json()

        # Odoo 側エラーをアプリ例外へ変換。
        if data.get("error"):
            raise OdooJsonRpcError(f"call_kw error: {data['error']}")

        # 正常時の result をそのまま返す。
        return data.get("result")


# ============================================================
# Odoo 実装（sale.order / pos.order）
# ============================================================


class OdooPosAdapter(PosAdapter):
    """Odoo 連携の POS アダプタ。

    routes 層からは本クラスの公開メソッドのみを利用し、
    Odoo モデル名や payload 形式の詳細を隠蔽する。
    """

    def __init__(self, cfg: OdooConfig) -> None:
        # ルーティング層から参照される設定。
        self.cfg = cfg
        # Odoo との実通信を担当する JSON-RPC クライアント。
        self.client = OdooJsonRpcClient(cfg)

    # -------------------------
    # 共通ユーティリティ
    # -------------------------

    def resolve_products_by_sku(self, skus: list[str]) -> dict[str, dict[str, Any]]:
        """SKU をキーに商品情報を解決する。

        戻り値:
            {
                "<sku>": {
                    "id": <product.product.id>,
                    "name": <商品名>,
                    "lst_price": <商品の既定単価>,
                }
            }

        Note:
            - sku_field は cfg.sku_field（default_code / barcode など）で切り替える。
            - lst_price は明細で単価未指定時のフォールバックとして使う。
        """
        field = self.cfg.sku_field
        rows = (
            self.client.call_kw(
                model="product.product",
                method="search_read",
                args=[
                    [[field, "in", skus]],
                    ["id", field, "name", "lst_price"],
                ],
                kwargs={"limit": max(1, len(skus))},
            )
            or []
        )

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = row.get(field)
            if key:
                out[str(key)] = {
                    "id": int(row["id"]),
                    "name": row.get("name"),
                    "lst_price": float(row.get("lst_price") or 0.0),
                }
        return out

    def resolve_product_ids_by_sku(self, skus: list[str]) -> dict[str, int]:
        """SKU -> product.product.id を解決する。

        Note:
            - cfg.sku_field により照合列を切り替え可能。
            - 戻り値は {sku文字列: product_id} のマッピング。
        """
        products = self.resolve_products_by_sku(skus)
        return {sku: int(data["id"]) for sku, data in products.items()}

    def _assert_pos_session_exists(self, session_id: int) -> None:
        """指定した POS セッションの存在と状態を検証する。

        Note:
            - closing_control / closed のセッションは同期対象として受け付けない。
        """
        rows = (
            self.client.call_kw(
                model="pos.session",
                method="search_read",
                args=[
                    [["id", "=", session_id]],
                    ["id", "state"],
                ],
                kwargs={"limit": 1},
            )
            or []
        )
        if not rows:
            raise OdooJsonRpcError(
                "Unknown POS session: "
                f"{session_id}. Odoo 側でセッション作成後に再実行してください。"
            )

        state = rows[0].get("state")
        if state in {"closing_control", "closed"}:
            raise OdooJsonRpcError(
                f"POS session {session_id} is not writable (state={state})."
            )

    # -------------------------
    # 案A：受注（sale.order）
    # -------------------------

    def create_sale_order_draft(
        self,
        partner_id: int,
        lines: list[CheckoutLine],
        pricelist_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> int:
        """sale.order を下書き（見積）で作成する。"""
        # 入力明細から SKU 一覧を抽出し、商品IDへ解決する。
        sku_list = [line.sku for line in lines]
        sku_to_pid = self.resolve_product_ids_by_sku(sku_list)

        # Odoo One2many コマンド形式の order_line を組み立てる。
        order_lines: list[tuple[int, int, dict[str, Any]]] = []
        for line in lines:
            pid = sku_to_pid.get(line.sku)
            if not pid:
                raise OdooJsonRpcError(f"Unknown SKU: {line.sku}")

            vals: dict[str, Any] = {
                "product_id": pid,
                "product_uom_qty": line.qty,
            }
            if line.price_unit is not None:
                vals["price_unit"] = line.price_unit

            order_lines.append((0, 0, vals))

        # sale.order.create に渡す本体値。
        so_vals: dict[str, Any] = {"partner_id": partner_id, "order_line": order_lines}
        if pricelist_id is not None:
            so_vals["pricelist_id"] = pricelist_id
        if note:
            so_vals["note"] = note

        # 下書き受注を作成し、作成IDを返す。
        so_id = self.client.call_kw("sale.order", "create", args=[so_vals])
        return int(so_id)

    def confirm_sale_order(self, sale_order_id: int) -> Any:
        """sale.order を確定する（action_confirm）。"""
        return self.client.call_kw(
            "sale.order",
            "action_confirm",
            args=[[sale_order_id]],
        )

    # -------------------------
    # 案B：POS（pos.order.sync_from_ui）
    # -------------------------

    def build_pos_order_payload(
        self,
        session_id: int,
        lines: list[CheckoutLine],
        partner_id: Optional[int],
        draft: bool = True,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """sync_from_ui に渡す 1件分の注文 payload を組み立てる。"""
        # POS 明細の SKU を商品情報へ解決する。
        sku_list = [line.sku for line in lines]
        sku_to_product = self.resolve_products_by_sku(sku_list)

        # sync_from_ui 用 lines（One2many コマンド形式）を生成する。
        pos_lines: list[list[Any]] = []
        order_total = 0.0
        for line in lines:
            product = sku_to_product.get(line.sku)
            if not product:
                raise OdooJsonRpcError(f"Unknown SKU: {line.sku}")

            unit_price = (
                float(line.price_unit)
                if line.price_unit is not None
                else float(product["lst_price"])
            )
            subtotal = round(unit_price * line.qty, 2)
            order_total += subtotal

            line_vals: dict[str, Any] = {
                "product_id": int(product["id"]),
                "qty": line.qty,
                "price_unit": unit_price,
                "discount": 0.0,
                "price_subtotal": subtotal,
                "price_subtotal_incl": subtotal,
                "tax_ids": [],
            }

            # One2many コマンド: [0, 0, vals]
            pos_lines.append([0, 0, line_vals])

        # sync_from_ui が受け取る order payload 本体（1件分）。
        order_uuid = str(uuid4())
        payload: dict[str, Any] = {
            "uuid": order_uuid,
            "session_id": session_id,
            "state": "draft" if draft else "paid",
            "partner_id": partner_id or False,
            "amount_total": round(order_total, 2),
            "amount_tax": 0.0,
            "amount_paid": 0.0 if draft else round(order_total, 2),
            "amount_return": 0.0,
            "lines": pos_lines,
        }
        if extra:
            # 呼び出し側から追加項目を注入できるようにする。
            payload.update(extra)
        return payload

    def create_pos_order_from_ui(
        self,
        session_id: int,
        lines: list[CheckoutLine],
        partner_id: Optional[int] = None,
        draft: bool = True,
        extra: Optional[dict[str, Any]] = None,
    ) -> Any:
        """pos.order.sync_from_ui を呼ぶ（Odoo 19 系）。"""
        # Odoo 19 の最小実装では、未決済の draft 同期を優先する。
        # draft=False は payment_ids 組み立ての版差が大きいため現時点では未対応。
        if not draft:
            raise OdooJsonRpcError(
                "mode='pos' は現在 draft=True のみ対応です。"
                "CREATE_POS_DRAFT=true を設定してください。"
            )

        self._assert_pos_session_exists(session_id)

        # まず版差調整可能な payload 生成処理を1か所に集約する。
        order_payload = self.build_pos_order_payload(
            session_id=session_id,
            lines=lines,
            partner_id=partner_id,
            draft=draft,
            extra=extra,
        )
        # sync_from_ui のシグネチャ: args=[[order_dict]]
        return self.client.call_kw(
            "pos.order",
            "sync_from_ui",
            args=[[order_payload]],
            kwargs={},
        )

    # -------------------------
    # API から呼ぶ入口（既定：sale.order）
    # -------------------------

    def checkout(self, req: CheckoutRequest) -> CheckoutResult:
        """既定のチェックアウト処理（sale.order 下書き→確定）。"""
        try:
            # 既定フロー: sale.order を作成する。
            so_id = self.create_sale_order_draft(
                partner_id=self.cfg.default_partner_id,
                lines=req.lines,
                pricelist_id=self.cfg.default_pricelist_id,
                note=req.note,
            )
            # 作成した受注を確定し、確認結果を保持する。
            confirm_result = self.confirm_sale_order(so_id)
            return CheckoutResult(
                ok=True,
                target="sale.order",
                record_id=so_id,
                raw={"confirm_result": confirm_result},
            )
        except Exception as exc:  # noqa: BLE001
            # 既定フロー失敗時も API 層が扱いやすい共通形式で返す。
            return CheckoutResult(
                ok=False,
                target="sale.order",
                record_id=None,
                raw=None,
                message=str(exc),
            )


def build_odoo_adapter(
    *,
    base_url: str,
    db: str,
    username: str,
    password: str,
    default_partner_id: int = 1,
    default_pricelist_id: Optional[int] = None,
    default_pos_session_id: Optional[int] = None,
    create_pos_draft: bool = True,
    sku_field: str = "default_code",
) -> OdooPosAdapter:
    """設定値から OdooPosAdapter を生成する補助関数。"""
    # 受け取った引数を OdooConfig に集約する。
    cfg = OdooConfig(
        base_url=base_url,
        db=db,
        username=username,
        password=password,
        default_partner_id=default_partner_id,
        default_pricelist_id=default_pricelist_id,
        default_pos_session_id=default_pos_session_id,
        create_pos_draft=create_pos_draft,
        sku_field=sku_field,
    )
    # API 層はこのヘルパーで依存注入しやすくなる。
    return OdooPosAdapter(cfg)
