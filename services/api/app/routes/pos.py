"""POS チェックアウト API ルート。

提供エンドポイント
- POST /pos/checkout

Odoo 連携モード
- mode="sale"（既定）: sale.order を下書き作成 → action_confirm で確定
- mode="pos"           : pos.order.create_from_ui で POS 注文作成（※ 版差が大きい）

設計方針
- POS 連携は adapters（pos_adapters/*）の内側に閉じ込める
- 環境変数 POS_ADAPTER により将来の差し替えを容易にする（dummy / odoo など）
- Codex で拡張しやすいよう、I/F と責務を明確にする
"""

from __future__ import annotations

import os
from typing import Any, Literal, Optional, overload

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.pos_adapters.odoo_jsonrpc import (
    CheckoutLine,
    CheckoutRequest,
    OdooConfig,
    OdooJsonRpcError,
    OdooPosAdapter,
)

router = APIRouter(prefix="/pos", tags=["pos"])
# このルーター配下の API は /pos/* として公開される。


# ============================================================
# リクエスト/レスポンス
# ============================================================


class CheckoutLineIn(BaseModel):
    """チェックアウト1行分の入力モデル。"""

    # 商品識別子。Odoo 側では cfg.sku_field（既定: default_code）で解決する。
    sku: str = Field(
        ...,
        description="SKU。既定は product.product.default_code として解決します。",
    )
    # 購入数量。0 以下は業務上無効なためバリデーションで拒否する。
    qty: float = Field(..., gt=0)
    # 単価。指定時は Odoo 既定価格を上書きする。
    price_unit: Optional[float] = Field(None, gt=0)


class CheckoutIn(BaseModel):
    """/pos/checkout の入力全体モデル。"""

    # 店舗や拠点の識別子。監査ログや将来のテナント分離に利用する想定。
    store_id: str = Field(..., description="店舗/テナント識別子")
    # 操作者ID。レジ担当などを紐づける任意フィールド。
    operator_id: Optional[str] = Field(None, description="操作者識別子（任意）")
    # 連携先モード。sale は受注経由、pos は create_from_ui 経由。
    mode: Literal["sale", "pos"] = Field(
        "sale",
        description='sale: sale.order, pos: pos.order.create_from_ui',
    )
    # 明細行の一覧。最低1行以上を想定して利用側で渡す。
    lines: list[CheckoutLineIn]
    # 伝票や注文に紐づける任意メモ。
    note: Optional[str] = None

    # mode="pos" のみで使用
    # POS セッションID。未指定時は環境変数 DEFAULT_POS_SESSION_ID を使う。
    pos_session_id: Optional[int] = Field(
        None,
        description=(
            "mode='pos' の場合に必要。未指定なら DEFAULT_POS_SESSION_ID を参照。"
        ),
    )
    # 顧客 partner_id。未指定時は環境変数 DEFAULT_PARTNER_ID（既定1）を使う。
    partner_id: Optional[int] = Field(
        None,
        description=(
            "顧客（partner）。未指定なら DEFAULT_PARTNER_ID を参照（既定: 店内客）。"
        ),
    )


class CheckoutOut(BaseModel):
    """/pos/checkout の標準レスポンス。"""

    # API 処理全体の成否。
    ok: bool
    # 実際に作成対象となった Odoo モデル名（sale.order / pos.order）。
    target: str
    # 作成レコードID。pos.create_from_ui のように即時IDが取れない場合は None。
    record_id: Optional[int] = None
    # Odoo からの生レスポンス（デバッグ/調査用途）。
    raw: Optional[Any] = None
    # 失敗時や補足情報を返すメッセージ。
    message: Optional[str] = None


# ============================================================
# アダプタ生成
# ============================================================


@overload
def _env(name: str) -> Optional[str]:
    """default 未指定時: 未設定なら None を返す。"""
    ...


@overload
def _env(name: str, default: str) -> str:
    """default 指定時: 未設定なら default を返す。"""
    ...


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """環境変数を取得する。

    Note:
        - 未設定または空文字の場合は default を返す。
        - default に str を渡した呼び出しでは、型上も str を返す。
    """
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _required_env(name: str) -> str:
    """必須の環境変数を取得する。未設定時は RuntimeError を送出する。"""
    # Optional[str] を str に絞り込むための共通ガード。
    value = _env(name)
    if value is None:
        raise RuntimeError(f"{name} が未設定です。")
    return value


def build_odoo_adapter_from_env() -> OdooPosAdapter:
    """環境変数から OdooPosAdapter を組み立てる。

    Note:
        - ODOO_URL/DB/USER/PASSWORD は必須。
        - 既定値のある項目は未設定時にフォールバックする。
    """
    # Odoo 接続に必須の接続情報。
    base_url = _required_env("ODOO_URL")
    db = _required_env("ODOO_DB")
    username = _required_env("ODOO_USER")
    password = _required_env("ODOO_PASSWORD")

    # sale.order 作成時に使う既定 partner_id（店内客など）。
    default_partner_id = int(_env("DEFAULT_PARTNER_ID", "1"))
    # 任意の価格表ID。未指定なら Odoo 既定ロジックに委譲。
    default_pricelist_id_raw = _env("DEFAULT_PRICELIST_ID")
    default_pricelist_id = (
        int(default_pricelist_id_raw) if default_pricelist_id_raw else None
    )

    # mode="pos" で利用する既定セッションID。
    default_pos_session_id_raw = _env("DEFAULT_POS_SESSION_ID")
    default_pos_session_id = (
        int(default_pos_session_id_raw) if default_pos_session_id_raw else None
    )

    # POS 伝票を draft 扱いで作るかどうかのフラグ。
    create_pos_draft = _env("CREATE_POS_DRAFT", "true").lower() == "true"
    # SKU 解決に使う Odoo フィールド（default_code / barcode など）。
    sku_field = _env("SKU_FIELD", "default_code")

    # アダプタ設定オブジェクト。routes 層から Odoo 実装詳細を隠蔽する。
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
    # 以降の業務処理はこの adapter インスタンスを介して実行する。
    return OdooPosAdapter(cfg)


# ============================================================
# ルート
# ============================================================


@router.post("/checkout", response_model=CheckoutOut)
def checkout(body: CheckoutIn) -> CheckoutOut:
    """チェックアウト明細を Odoo に登録する。

    処理フロー:
        1. 環境変数からアダプタ設定を構築
        2. 入力明細を adapter 用モデルへ変換
        3. mode に応じて sale.order または pos.order を作成
    """

    # 将来: POS_ADAPTER により dummy 等へ差し替え可能にする
    # 現在の実装は odoo のみ許可する。
    adapter_name = _env("POS_ADAPTER", "odoo")
    if adapter_name != "odoo":
        raise HTTPException(
            status_code=400,
            detail=f"未対応の POS_ADAPTER です: {adapter_name}",
        )

    # Odoo 接続済みアダプタを生成する。
    adapter = build_odoo_adapter_from_env()

    # 入力行をアダプタ用に変換
    # body.lines（HTTP 入力） -> CheckoutLine（アプリ境界内モデル）
    lines = [
        CheckoutLine(sku=line.sku, qty=line.qty, price_unit=line.price_unit)
        for line in body.lines
    ]

    try:
        if body.mode == "sale":
            # 受注（sale.order）: 下書き→確定
            # routes 層は I/O のみ担当し、Odoo 呼び出し詳細は adapter に委譲する。
            result = adapter.checkout(
                CheckoutRequest(
                    # どの店舗・誰の操作かをログや追跡に使える形で渡す。
                    store_id=body.store_id,
                    operator_id=body.operator_id,
                    lines=lines,
                    note=body.note,
                )
            )
            return CheckoutOut(
                # adapter の標準結果を API レスポンスへそのまま写像する。
                ok=result.ok,
                target=result.target,
                record_id=result.record_id,
                raw=result.raw,
                message=result.message,
            )

        # POS（create_from_ui）
        # リクエスト優先でセッションIDを決定し、なければ既定値へフォールバック。
        pos_session_id = body.pos_session_id or adapter.cfg.default_pos_session_id
        if not pos_session_id:
            raise HTTPException(
                status_code=400,
                detail="mode='pos' の場合は pos_session_id が必要です。",
            )

        # 顧客はリクエスト指定を優先し、未指定時は既定顧客を利用する。
        partner_id = body.partner_id or adapter.cfg.default_partner_id
        # create_from_ui の payload 組み立て/呼び出しは adapter 側で吸収する。
        raw = adapter.create_pos_order_from_ui(
            session_id=pos_session_id,
            lines=lines,
            partner_id=partner_id,
            draft=adapter.cfg.create_pos_draft,
            extra={
                # 必要に応じて POS 側の追加フィールドを入れる
                # 例: "note": body.note
            },
        )
        return CheckoutOut(ok=True, target="pos.order", record_id=None, raw=raw)

    except OdooJsonRpcError as exc:
        # Odoo 側エラーは upstream 障害として 502 を返す。
        raise HTTPException(status_code=502, detail=f"Odoo エラー: {exc}") from exc
    except HTTPException:
        # 明示的な業務エラーはそのまま透過。
        raise
    except Exception as exc:  # noqa: BLE001
        # 想定外エラーは 500 に集約し、原因文字列を返す。
        raise HTTPException(status_code=500, detail=str(exc)) from exc
