"""Odoo 管理系 API ルート。

提供エンドポイント
- POST /admin/odoo/sync-products

設計方針
- routes 層は HTTP I/O と認可判定を担当する
- Odoo 呼び出しは pos_adapters 層へ委譲する
- キャッシュ保存は models 層へ委譲する
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, overload

from app.models.odoo_product_cache import get_odoo_product_cache_store
from app.pos_adapters.odoo_jsonrpc import OdooConfig, OdooJsonRpcError, OdooPosAdapter
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/admin/odoo", tags=["admin-odoo"])


class SyncProductsIn(BaseModel):
    """`POST /admin/odoo/sync-products` の入力モデル。"""

    # Odoo から取得する上限件数。
    limit: int = Field(500, ge=1, le=5000)
    # 差分同期の開始時刻（ISO8601、任意）。
    updated_since: Optional[str] = None


class SyncProductsOut(BaseModel):
    """`POST /admin/odoo/sync-products` のレスポンスモデル。"""

    # API 処理全体の成否。
    ok: bool
    # 保存した SKU 件数。
    count: int
    # 同期時刻（ISO8601）。
    synced_at: str
    # 空 SKU で除外した件数。
    skipped_empty_sku_count: int
    # 重複 SKU 件数（後勝ちで上書き）。
    duplicate_sku_count: int


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
    """
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _required_env(name: str) -> str:
    """必須の環境変数を取得する。未設定時は RuntimeError を送出する。"""
    value = _env(name)
    if value is None:
        raise RuntimeError(f"{name} が未設定です。")
    return value


def _is_development_env() -> bool:
    """管理 API を簡易開放する開発環境かどうかを返す。"""
    api_env = _env("API_ENV", "development").lower()
    return api_env in {"dev", "development", "local", "test"}


def _assert_admin_access(admin_token_header: Optional[str]) -> None:
    """管理 API のアクセス可否を判定する。

    Note:
        - 開発環境（API_ENV=development 系）はトークンなし許可。
        - それ以外の環境は `X-Admin-Token` と `ADMIN_API_TOKEN` の一致を必須とする。
    """
    if _is_development_env():
        return

    expected_token = _env("ADMIN_API_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_API_TOKEN が未設定です。管理APIを有効化できません。",
        )

    if admin_token_header != expected_token:
        raise HTTPException(status_code=401, detail="管理APIトークンが不正です。")


def build_odoo_adapter_from_env() -> OdooPosAdapter:
    """環境変数から OdooPosAdapter を組み立てる。"""
    cfg = OdooConfig(
        base_url=_required_env("ODOO_URL"),
        db=_required_env("ODOO_DB"),
        username=_required_env("ODOO_USER"),
        password=_required_env("ODOO_PASSWORD"),
    )
    return OdooPosAdapter(cfg)


@router.post("/sync-products", response_model=SyncProductsOut)
def sync_products(
    body: SyncProductsIn,
    admin_token_header: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> SyncProductsOut:
    """Odoo 商品情報を取得し、ローカルキャッシュへ同期する。"""
    _assert_admin_access(admin_token_header)
    adapter = build_odoo_adapter_from_env()

    try:
        rows = adapter.fetch_products_for_cache(
            limit=body.limit,
            updated_since=body.updated_since,
        )
        sync_result = get_odoo_product_cache_store().replace_from_odoo_rows(
            rows=rows,
            synced_at=datetime.now(timezone.utc),
        )
    except OdooJsonRpcError as exc:
        raise HTTPException(status_code=502, detail=f"Odoo エラー: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SyncProductsOut(
        ok=True,
        count=sync_result.count,
        synced_at=sync_result.synced_at,
        skipped_empty_sku_count=sync_result.skipped_empty_sku_count,
        duplicate_sku_count=sync_result.duplicate_sku_count,
    )
