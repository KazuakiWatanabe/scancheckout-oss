"""Odoo 商品キャッシュの永続化ストア。

本モジュールは Odoo の `product.product` 情報を
`storage/odoo_product_cache.json` に保存し、以下を担当する。
- キャッシュ JSON の読み書き
- SKU（default_code）をキーにした商品情報参照
- 同期結果の集計（空SKU除外、重複SKUの後勝ち）

Note:
    - 外部 API との通信は行わない。Odoo 呼び出しは adapter 層の責務。
    - 同一 SKU が複数件ある場合は「後勝ち」で上書きする。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional

CACHE_VERSION = 1


@dataclass(frozen=True)
class OdooProductCacheItem:
    """SKU 単位の商品キャッシュ1件を表す。

    主要変数:
        product_id: Odoo `product.product.id`。
        name: 商品名（UI 表示向け）。
        active: Odoo 側の有効フラグ。
        barcode: バーコード（未設定時は None）。
        list_price: 参照用の単価。
    """

    product_id: int
    name: str
    active: bool
    barcode: Optional[str]
    list_price: float


@dataclass(frozen=True)
class OdooProductCacheSnapshot:
    """キャッシュ全体の読み取り結果を表す。

    主要変数:
        version: JSON スキーマバージョン。
        synced_at: 最終同期時刻（ISO8601）。
        items: SKU をキーにした商品キャッシュ辞書。
    """

    version: int
    synced_at: Optional[str]
    items: dict[str, OdooProductCacheItem]


@dataclass(frozen=True)
class OdooProductCacheSyncResult:
    """同期保存処理の集計結果を表す。

    主要変数:
        count: 保存された SKU 件数。
        synced_at: 保存時刻（ISO8601）。
        skipped_empty_sku_count: 空 SKU として除外した件数。
        duplicate_sku_count: 重複 SKU の件数。
    """

    count: int
    synced_at: str
    skipped_empty_sku_count: int
    duplicate_sku_count: int


def _normalize_sku(value: Any) -> Optional[str]:
    """SKU 文字列を正規化して返す。

    Note:
        - None や空白のみは None を返す（同期対象外）。
    """
    if value is None:
        return None
    sku = str(value).strip()
    return sku if sku else None


def _to_list_price(value: Any) -> float:
    """単価値を float へ正規化する。"""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


class OdooProductCacheStore:
    """Odoo 商品キャッシュを JSON ファイルで管理するストア。"""

    def __init__(self, file_path: Path) -> None:
        """ストアを初期化する。

        主要変数:
            file_path: キャッシュ JSON の保存先パス。
        """
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def read_snapshot(self) -> OdooProductCacheSnapshot:
        """キャッシュ JSON を読み取り、スナップショットを返す。"""
        with self._lock:
            if not self._file_path.exists():
                return OdooProductCacheSnapshot(
                    version=CACHE_VERSION,
                    synced_at=None,
                    items={},
                )

            raw = json.loads(self._file_path.read_text(encoding="utf-8"))
            items_raw = raw.get("items") or {}
            items: dict[str, OdooProductCacheItem] = {}
            for sku, data in items_raw.items():
                normalized_sku = _normalize_sku(sku)
                if not normalized_sku:
                    continue
                items[normalized_sku] = OdooProductCacheItem(
                    product_id=int(data["product_id"]),
                    name=str(data.get("name") or normalized_sku),
                    active=bool(data.get("active", True)),
                    barcode=str(data["barcode"]) if data.get("barcode") else None,
                    list_price=_to_list_price(data.get("list_price")),
                )

            return OdooProductCacheSnapshot(
                version=int(raw.get("version", CACHE_VERSION)),
                synced_at=str(raw["synced_at"]) if raw.get("synced_at") else None,
                items=items,
            )

    def replace_from_odoo_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        synced_at: datetime,
    ) -> OdooProductCacheSyncResult:
        """Odoo 取得結果でキャッシュ全体を置き換える。

        Note:
            - 同一 SKU は後勝ちで上書きする。
            - SKU が空/None の行は除外する。
        """
        items: dict[str, OdooProductCacheItem] = {}
        skipped_empty_sku_count = 0
        duplicate_skus: set[str] = set()

        for row in rows:
            sku = _normalize_sku(row.get("default_code"))
            if not sku:
                skipped_empty_sku_count += 1
                continue

            if sku in items:
                duplicate_skus.add(sku)

            list_price = row.get("list_price")
            if list_price is None:
                list_price = row.get("lst_price")

            items[sku] = OdooProductCacheItem(
                product_id=int(row["id"]),
                name=str(row.get("name") or sku),
                active=bool(row.get("active", True)),
                barcode=str(row["barcode"]) if row.get("barcode") else None,
                list_price=_to_list_price(list_price),
            )

        snapshot = {
            "version": CACHE_VERSION,
            "synced_at": synced_at.isoformat(),
            "items": {
                sku: {
                    "product_id": item.product_id,
                    "name": item.name,
                    "active": item.active,
                    "barcode": item.barcode,
                    "list_price": item.list_price,
                }
                for sku, item in sorted(items.items())
            },
        }
        with self._lock:
            self._file_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return OdooProductCacheSyncResult(
            count=len(items),
            synced_at=snapshot["synced_at"],
            skipped_empty_sku_count=skipped_empty_sku_count,
            duplicate_sku_count=len(duplicate_skus),
        )

    def get_name_map(self, skus: list[str]) -> dict[str, str]:
        """SKU 一覧に対応する商品名マップを返す。"""
        snapshot = self.read_snapshot()
        out: dict[str, str] = {}
        for sku in skus:
            normalized_sku = _normalize_sku(sku)
            if not normalized_sku:
                continue
            item = snapshot.items.get(normalized_sku)
            if item:
                out[normalized_sku] = item.name
        return out

    def resolve_products_by_sku(self, skus: list[str]) -> dict[str, dict[str, Any]]:
        """SKU 一覧をキャッシュから product 情報へ解決する。

        戻り値:
            {
                "<sku>": {
                    "id": <product_id>,
                    "name": <商品名>,
                    "lst_price": <単価>,
                }
            }
        """
        snapshot = self.read_snapshot()
        out: dict[str, dict[str, Any]] = {}
        for sku in skus:
            normalized_sku = _normalize_sku(sku)
            if not normalized_sku:
                continue
            item = snapshot.items.get(normalized_sku)
            if not item:
                continue
            out[normalized_sku] = {
                "id": item.product_id,
                "name": item.name,
                "lst_price": item.list_price,
            }
        return out


_ODOO_PRODUCT_CACHE_STORE: Optional[OdooProductCacheStore] = None


def get_odoo_product_cache_store() -> OdooProductCacheStore:
    """Odoo 商品キャッシュストアのシングルトンを返す。"""
    global _ODOO_PRODUCT_CACHE_STORE
    if _ODOO_PRODUCT_CACHE_STORE is None:
        _ODOO_PRODUCT_CACHE_STORE = OdooProductCacheStore(
            file_path=Path("storage/odoo_product_cache.json")
        )
    return _ODOO_PRODUCT_CACHE_STORE
