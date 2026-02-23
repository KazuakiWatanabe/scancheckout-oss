"""Odoo 商品キャッシュストアの単体テスト。

検証対象:
- キャッシュ JSON の read/write
- 空 SKU の除外
- 重複 SKU の後勝ちポリシー
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.odoo_product_cache import OdooProductCacheStore


def test_replace_from_odoo_rows_writes_expected_format(tmp_path) -> None:
    """Odoo 行からキャッシュ JSON が想定形式で保存されることを確認する。"""
    store = OdooProductCacheStore(file_path=tmp_path / "odoo_product_cache.json")
    synced_at = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)

    result = store.replace_from_odoo_rows(
        rows=[
            {
                "id": 101,
                "default_code": "ANPAN-001",
                "name": "あんぱん",
                "active": True,
                "barcode": "111",
                "lst_price": 150.0,
            },
            {
                "id": 102,
                "default_code": " ",
                "name": "skip-empty",
                "active": True,
                "barcode": None,
                "lst_price": 200.0,
            },
            {
                "id": 103,
                "default_code": None,
                "name": "skip-none",
                "active": False,
                "barcode": None,
                "lst_price": 220.0,
            },
            {
                "id": 104,
                "default_code": "ANPAN-001",
                "name": "あんぱん(新版)",
                "active": False,
                "barcode": "999",
                "lst_price": 180.0,
            },
        ],
        synced_at=synced_at,
    )

    assert result.count == 1
    assert result.synced_at == synced_at.isoformat()
    assert result.skipped_empty_sku_count == 2
    assert result.duplicate_sku_count == 1

    snapshot = store.read_snapshot()
    assert snapshot.version == 1
    assert snapshot.synced_at == synced_at.isoformat()
    assert list(snapshot.items.keys()) == ["ANPAN-001"]

    # 同一 SKU は後勝ち（後続の id=104 が採用される）。
    item = snapshot.items["ANPAN-001"]
    assert item.product_id == 104
    assert item.name == "あんぱん(新版)"
    assert item.active is False
    assert item.barcode == "999"
    assert item.list_price == 180.0


def test_resolve_products_by_sku_reads_cache_entries(tmp_path) -> None:
    """キャッシュ済み SKU だけを product 情報へ解決できることを確認する。"""
    store = OdooProductCacheStore(file_path=tmp_path / "odoo_product_cache.json")
    store.replace_from_odoo_rows(
        rows=[
            {
                "id": 201,
                "default_code": "BREAD-001",
                "name": "食パン",
                "active": True,
                "barcode": None,
                "lst_price": 120.0,
            }
        ],
        synced_at=datetime(2026, 2, 22, 1, 0, 0, tzinfo=timezone.utc),
    )

    resolved = store.resolve_products_by_sku(["BREAD-001", "UNKNOWN-001"])

    assert resolved == {
        "BREAD-001": {
            "id": 201,
            "name": "食パン",
            "lst_price": 120.0,
        }
    }
