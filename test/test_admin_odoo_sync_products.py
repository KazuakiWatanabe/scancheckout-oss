"""Odoo 商品キャッシュ同期 API のテスト。

検証対象:
- POST /admin/odoo/sync-products の同期処理
- 管理APIトークンのガード挙動
"""

from __future__ import annotations

from typing import Any, Optional

import app.routes.admin_odoo as admin_odoo_module
from app.models.odoo_product_cache import get_odoo_product_cache_store
from fastapi.testclient import TestClient


class _FakeOdooAdapter:
    """テスト用の Odoo adapter スタブ。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.calls: list[dict[str, Any]] = []

    def fetch_products_for_cache(
        self,
        *,
        limit: int = 500,
        updated_since: Optional[str] = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """同期対象の商品行を返す。"""
        self.calls.append(
            {
                "limit": limit,
                "updated_since": updated_since,
                "offset": offset,
            }
        )
        return self._rows


def test_sync_products_endpoint_creates_cache(
    client: TestClient,
    monkeypatch,
) -> None:
    """同期 API が Odoo 行をキャッシュへ保存することを確認する。"""
    rows = [
        {
            "id": 301,
            "default_code": "ANPAN-001",
            "name": "あんぱん",
            "active": True,
            "barcode": "111",
            "lst_price": 150.0,
        },
        {
            "id": 302,
            "default_code": None,
            "name": "skip",
            "active": True,
            "barcode": None,
            "lst_price": 200.0,
        },
        {
            "id": 303,
            "default_code": "ANPAN-001",
            "name": "あんぱん(改)",
            "active": True,
            "barcode": "222",
            "lst_price": 180.0,
        },
    ]
    holder: dict[str, _FakeOdooAdapter] = {}

    def _fake_builder() -> _FakeOdooAdapter:
        adapter = _FakeOdooAdapter(rows=rows)
        holder["adapter"] = adapter
        return adapter

    monkeypatch.setattr(admin_odoo_module, "build_odoo_adapter_from_env", _fake_builder)

    response = client.post(
        "/admin/odoo/sync-products",
        json={"limit": 123, "updated_since": "2026-02-21T00:00:00+09:00"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["skipped_empty_sku_count"] == 1
    assert payload["duplicate_sku_count"] == 1
    assert isinstance(payload["synced_at"], str)

    adapter = holder["adapter"]
    assert adapter.calls == [
        {
            "limit": 123,
            "updated_since": "2026-02-21T00:00:00+09:00",
            "offset": 0,
        }
    ]

    snapshot = get_odoo_product_cache_store().read_snapshot()
    assert list(snapshot.items.keys()) == ["ANPAN-001"]
    assert snapshot.items["ANPAN-001"].product_id == 303
    assert snapshot.items["ANPAN-001"].name == "あんぱん(改)"


def test_sync_products_requires_token_outside_development(
    client: TestClient,
    monkeypatch,
) -> None:
    """開発環境以外では管理APIトークンが必須であることを確認する。"""
    monkeypatch.setenv("API_ENV", "production")
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret-token")

    monkeypatch.setattr(
        admin_odoo_module,
        "build_odoo_adapter_from_env",
        lambda: _FakeOdooAdapter(rows=[]),
    )

    no_token_response = client.post("/admin/odoo/sync-products", json={"limit": 1})
    assert no_token_response.status_code == 401

    invalid_token_response = client.post(
        "/admin/odoo/sync-products",
        json={"limit": 1},
        headers={"X-Admin-Token": "wrong-token"},
    )
    assert invalid_token_response.status_code == 401

    valid_token_response = client.post(
        "/admin/odoo/sync-products",
        json={"limit": 1},
        headers={"X-Admin-Token": "secret-token"},
    )
    assert valid_token_response.status_code == 200
