"""商品画像ストアの単体テスト。

検証対象:
- 画像メタデータの登録・検索・削除
- index.json への永続化形式
- SKU 正規化の入力制約
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.models.product_image_store import (
    INDEX_FILENAME,
    ProductImageStore,
    normalize_sku,
)


def test_store_create_list_and_delete(tmp_path: Path) -> None:
    """画像登録から削除までの一連処理が成立することを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)

    record = store.create_image(
        sku="BREAD-001",
        content_type="image/png",
        image_bytes=b"png-bytes",
        note="包装違い",
    )
    assert record.sku == "BREAD-001"
    assert record.filename.endswith(".png")
    assert record.note == "包装違い"

    listed = store.list_images(sku="BREAD-001")
    assert len(listed) == 1
    assert listed[0].image_id == record.image_id

    image_path = store.get_image_path(record.image_id)
    assert image_path is not None
    assert image_path.exists()
    assert image_path.read_bytes() == b"png-bytes"

    deleted = store.delete_image(record.image_id)
    assert deleted is True
    assert store.get_image(record.image_id) is None
    assert not image_path.exists()


def test_store_writes_index_json(tmp_path: Path) -> None:
    """登録後に index.json が所定フォーマットで保存されることを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)

    record = store.create_image(
        sku="TEST-SKU",
        content_type="image/jpeg",
        image_bytes=b"jpeg-bytes",
        note=None,
    )

    index_path = root_dir / INDEX_FILENAME
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["image_id"] == record.image_id
    assert payload["items"][0]["sku"] == "TEST-SKU"
    assert payload["items"][0]["content_type"] == "image/jpeg"


def test_normalize_sku_rejects_invalid_chars() -> None:
    """SKU 正規化で不正文字列を拒否することを確認する。"""
    with pytest.raises(ValueError):
        normalize_sku("../invalid")

    with pytest.raises(ValueError):
        normalize_sku(" ")
