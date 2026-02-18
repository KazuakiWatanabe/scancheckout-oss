"""POS チェックアウト API ルート。

提供エンドポイント
- POST /pos/checkout

Odoo 連携モード
- mode="sale"（既定）: sale.order を下書き作成 → action_confirm で確定
- mode="pos"           : 現フェーズ未対応（HTTP 400 を返す）

設計方針
- POS 連携は adapters（pos_adapters/*）の内側に閉じ込める
- 環境変数 POS_ADAPTER により将来の差し替えを容易にする（dummy / odoo など）
- OdooJsonRpcError は HTTP 502、その他の例外は HTTP 500 に集約する
- レスポンス形式: {ok, target, record_id, message} に固定する
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from app.pos_adapters.odoo_jsonrpc import (
    CheckoutLine,
    OdooConfig,
    OdooJsonRpcError,
    OdooPosAdapter,
)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    # 連携先モード。現フェーズは sale のみ対応。pos を指定すると 400 を返す。
    mode: Literal["sale", "pos"] = Field(
        "sale",
        description="sale: sale.order（対応済）/ pos: 現フェーズ未対応（400）",
    )
    # 明細行の一覧。最低1行以上を想定して利用側で渡す。
    lines: list[CheckoutLineIn]
    # 伝票や注文に紐づける任意メモ。
    note: Optional[str] = None


class CheckoutOut(BaseModel):
    """/pos/checkout の標準レスポンス。

    Note:
        - エラー時は ok=False ではなく HTTP 4xx/5xx を返すため、
          正常系では ok は常に True となる。
        - target は作成した Odoo モデル名（現フェーズは "sale.order" 固定）。
    """

    # API 処理全体の成否。
    ok: bool
    # 実際に作成対象となった Odoo モデル名（現フェーズは "sale.order"）。
    target: str
    # 作成レコードID。取得できない場合は None。
    record_id: Optional[int] = None
    # エラーや補足情報のメッセージ（通常は None）。
    message: Optional[str] = None


# ============================================================
# アダプタ生成
# ============================================================


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """環境変数を取得する。

    Note:
        - 未設定または空文字の場合は default を返す。
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
        - ODOO_URL / ODOO_DB / ODOO_USER / ODOO_PASSWORD は必須。
        - 既定値のある項目は未設定時にフォールバックする。
    """
    # Odoo 接続に必須の接続情報。
    base_url = _required_env("ODOO_URL")
    db = _required_env("ODOO_DB")
    username = _required_env("ODOO_USER")
    password = _required_env("ODOO_PASSWORD")

    # sale.order 作成時に使う既定 partner_id（店内客など）。
    default_partner_id = int(_env("DEFAULT_PARTNER_ID", "1"))  # type: ignore[arg-type]
    # 任意の価格表ID。未指定なら Odoo 既定ロジックに委譲。
    default_pricelist_id_raw = _env("DEFAULT_PRICELIST_ID")
    default_pricelist_id = (
        int(default_pricelist_id_raw) if default_pricelist_id_raw else None
    )
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
        1. mode="pos" を先行ブロック（400）
        2. 環境変数からアダプタ設定を構築
        3. 入力明細を adapter 用モデルへ変換
        4. sale.order を下書き作成 → action_confirm で確定

    エラー:
        - mode="pos": HTTP 400
        - OdooJsonRpcError: HTTP 502（Odoo 側の障害）
        - その他の例外: HTTP 500
    """
    # 現フェーズでは mode="pos" は未対応。明示的に 400 を返す。
    if body.mode == "pos":
        raise HTTPException(
            status_code=400,
            detail="mode='pos' は現フェーズ未対応です。mode='sale' を指定してください。",
        )

    # Odoo 接続済みアダプタを生成する。
    adapter = build_odoo_adapter_from_env()

    # 入力行をアダプタ用モデルへ変換する。
    # body.lines（HTTP 入力） -> CheckoutLine（アプリ境界内モデル）
    lines = [
        CheckoutLine(sku=line.sku, qty=line.qty, price_unit=line.price_unit)
        for line in body.lines
    ]

    try:
        # 受注（sale.order）: 下書き作成 → 確定。
        # adapter の個別メソッドを呼ぶことで OdooJsonRpcError を routes 層まで伝播させる。
        so_id = adapter.create_sale_order_draft(
            partner_id=adapter.cfg.default_partner_id,
            lines=lines,
            pricelist_id=adapter.cfg.default_pricelist_id,
            note=body.note,
        )
        adapter.confirm_sale_order(so_id)
        return CheckoutOut(
            ok=True,
            target="sale.order",
            record_id=so_id,
        )

    except OdooJsonRpcError as exc:
        # Odoo 側エラーは upstream 障害として 502 を返す。
        raise HTTPException(status_code=502, detail=f"Odoo エラー: {exc}") from exc
    except HTTPException:
        # 明示的な業務エラーはそのまま透過させる。
        raise
    except Exception as exc:  # noqa: BLE001
        # 想定外エラーは 500 に集約し、原因文字列を返す。
        raise HTTPException(status_code=500, detail=str(exc)) from exc
