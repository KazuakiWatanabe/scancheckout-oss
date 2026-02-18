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
  - create_from_ui（※ Odoo の版差が大きいのでスケルトン）

注意
- POS の create_from_ui に渡す payload は Odoo バージョンや導入モジュールで変わります。
  実運用では POS 画面で注文した際の Network ペイロードを DevTools で確認し、
  build_pos_order_payload() を合わせるのが最短です。
- SKU は既定で product.product.default_code を使用します（cfg.sku_field で変更可能）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

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

    # POS 用の既定値（create_from_ui のみ）
    # mode="pos" でセッションID未指定時に使う値。
    default_pos_session_id: Optional[int] = None
    # create_from_ui 呼び出し時に draft フラグへ反映する値。
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

    def resolve_product_ids_by_sku(self, skus: list[str]) -> dict[str, int]:
        """SKU -> product.product.id を解決する。

        Note:
            - cfg.sku_field により照合列を切り替え可能。
            - 戻り値は {sku文字列: product_id} のマッピング。
        """
        # SKU 照合に使うフィールド名（default_code / barcode など）。
        field = self.cfg.sku_field

        # 対象 SKU 群を一括で search_read する。
        rows = self.client.call_kw(
            model="product.product",
            method="search_read",
            args=[
                [[field, "in", skus]],
                ["id", field, "name"],
            ],
            kwargs={"limit": max(1, len(skus))},
        ) or []

        # SKU -> product_id の辞書を組み立てる。
        out: dict[str, int] = {}
        for row in rows:
            # row[field] が実際の SKU 値。
            key = row.get(field)
            if key:
                out[str(key)] = int(row["id"])
        return out

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
    # 案B：POS（pos.order.create_from_ui）
    # -------------------------

    def build_pos_order_payload(
        self,
        session_id: int,
        lines: list[CheckoutLine],
        partner_id: Optional[int],
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """create_from_ui に渡す payload を組み立てる（要：版差調整）。"""
        # POS 明細の SKU を商品IDへ解決する。
        sku_list = [line.sku for line in lines]
        sku_to_pid = self.resolve_product_ids_by_sku(sku_list)

        # create_from_ui 用 lines（One2many コマンド形式）を生成する。
        pos_lines: list[list[Any]] = []
        for line in lines:
            pid = sku_to_pid.get(line.sku)
            if not pid:
                raise OdooJsonRpcError(f"Unknown SKU: {line.sku}")

            line_vals: dict[str, Any] = {"product_id": pid, "qty": line.qty}
            if line.price_unit is not None:
                line_vals["price_unit"] = line.price_unit

            # One2many コマンド: [0, 0, vals]
            pos_lines.append([0, 0, line_vals])

        # create_from_ui が受け取る order payload 本体。
        payload: dict[str, Any] = {
            "data": {
                # フィールド名も版差があるため、実際の payload に合わせて修正する
                "pos_session_id": session_id,
                "partner_id": partner_id or False,
                "lines": pos_lines,
            }
        }
        if extra:
            # 呼び出し側から追加項目を注入できるようにする。
            payload["data"].update(extra)
        return payload

    def create_pos_order_from_ui(
        self,
        session_id: int,
        lines: list[CheckoutLine],
        partner_id: Optional[int] = None,
        draft: bool = True,
        extra: Optional[dict[str, Any]] = None,
    ) -> Any:
        """pos.order.create_from_ui を呼ぶ（要：payload 調整）。"""
        # まず版差調整可能な payload 生成処理を1か所に集約する。
        order_payload = self.build_pos_order_payload(
            session_id=session_id,
            lines=lines,
            partner_id=partner_id,
            extra=extra,
        )
        # create_from_ui のシグネチャに合わせて args を構成して呼び出す。
        return self.client.call_kw(
            "pos.order",
            "create_from_ui",
            args=[[order_payload], draft],
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
