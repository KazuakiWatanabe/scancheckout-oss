"""商品画像ストアの単体テスト。

検証対象:
- 画像メタデータの登録・検索・削除
- index.json への永続化形式
- phash の保存と遅延計算
- SKU 正規化の入力制約
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from app.models.product_image_store import (
    INDEX_FILENAME,
    ProductImageStore,
    normalize_sku,
)
from PIL import Image


def _sample_image_bytes(*, image_format: str) -> bytes:
    """テスト用の小さな画像バイト列を返す。"""
    image = Image.new("RGB", (16, 16), color=(240, 180, 90))
    image.putpixel((4, 4), (20, 20, 20))
    image.putpixel((12, 12), (10, 10, 200))
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def test_store_create_list_and_delete(tmp_path: Path) -> None:
    """画像登録から削除までの一連処理が成立することを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)
    image_bytes = _sample_image_bytes(image_format="PNG")

    record = store.create_image(
        sku="BREAD-001",
        content_type="image/png",
        image_bytes=image_bytes,
        note="包装違い",
    )
    assert record.sku == "BREAD-001"
    assert record.filename.endswith(".png")
    assert record.note == "包装違い"
    assert isinstance(record.phash, str)
    assert len(record.phash) == 16

    listed = store.list_images(sku="BREAD-001")
    assert len(listed) == 1
    assert listed[0].image_id == record.image_id

    image_path = store.get_image_path(record.image_id)
    assert image_path is not None
    assert image_path.exists()
    assert image_path.read_bytes() == image_bytes

    deleted = store.delete_image(record.image_id)
    assert deleted is True
    assert store.get_image(record.image_id) is None
    assert not image_path.exists()


def test_store_writes_index_json(tmp_path: Path) -> None:
    """登録後に index.json が所定フォーマットで保存されることを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)
    image_bytes = _sample_image_bytes(image_format="JPEG")

    record = store.create_image(
        sku="TEST-SKU",
        content_type="image/jpeg",
        image_bytes=image_bytes,
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
    assert isinstance(payload["items"][0]["phash"], str)
    assert len(payload["items"][0]["phash"]) == 16


def test_store_lazy_updates_missing_phash_on_listing(tmp_path: Path) -> None:
    """既存 index の phash 欠損項目が遅延計算で補完されることを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)

    record = store.create_image(
        sku="LAZY-001",
        content_type="image/png",
        image_bytes=_sample_image_bytes(image_format="PNG"),
        note=None,
    )
    index_path = root_dir / INDEX_FILENAME
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["items"][0]["phash"] = None
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    reloaded = ProductImageStore(root_dir=root_dir)
    hashes = reloaded.list_sku_phashes(allowed_skus={"LAZY-001"})

    assert "LAZY-001" in hashes
    assert len(hashes["LAZY-001"]) == 1
    assert len(hashes["LAZY-001"][0]) == 16

    updated_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert updated_payload["items"][0]["image_id"] == record.image_id
    assert isinstance(updated_payload["items"][0]["phash"], str)


def test_normalize_sku_rejects_invalid_chars() -> None:
    """SKU 正規化で不正文字列を拒否することを確認する。"""
    with pytest.raises(ValueError):
        normalize_sku("../invalid")

    with pytest.raises(ValueError):
        normalize_sku(" ")
