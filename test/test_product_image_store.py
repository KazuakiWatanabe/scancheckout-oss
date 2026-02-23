"""商品画像ストアの単体テスト。

検証対象:
- 画像メタデータの登録・検索・削除
- index.json への pHash 保存
- Embedding ストアへの保存
- 既存データ（phash欠損）の遅延補完
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from app.models import product_embedding_store as product_embedding_store_module
from app.models.product_embedding_store import ProductEmbeddingStore
from app.models.product_image_store import (
    INDEX_FILENAME,
    ProductImageStore,
    normalize_sku,
)
from app.vision import embedding as embedding_module
from PIL import Image, ImageDraw


def _sample_png_bytes() -> bytes:
    """テスト用の簡易 PNG 画像を返す。"""
    image = Image.new("RGB", (32, 32), color=(240, 220, 80))
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 16, 16), fill=(10, 10, 10))
    draw.rectangle((18, 18, 28, 28), fill=(100, 20, 20))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_store_create_list_and_delete(tmp_path: Path, monkeypatch) -> None:
    """画像登録から削除までの一連処理が成立することを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)
    product_embedding_store_module._PRODUCT_EMBEDDING_STORE = ProductEmbeddingStore(
        file_path=root_dir / "embeddings.json"
    )

    monkeypatch.setattr(
        embedding_module,
        "compute_embedding_vector",
        lambda image_bytes, model_name, model_path, input_size: [1.0, 0.0, 0.0],
    )

    record = store.create_image(
        sku="BREAD-001",
        content_type="image/png",
        image_bytes=_sample_png_bytes(),
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

    embedding_store = ProductEmbeddingStore(file_path=root_dir / "embeddings.json")
    vector = embedding_store.get_embedding(record.image_id)
    assert vector == [1.0, 0.0, 0.0]

    image_path = store.get_image_path(record.image_id)
    assert image_path is not None
    assert image_path.exists()

    deleted = store.delete_image(record.image_id)
    assert deleted is True
    assert store.get_image(record.image_id) is None
    assert not image_path.exists()
    product_embedding_store_module._PRODUCT_EMBEDDING_STORE = None


def test_store_writes_index_json_with_phash(tmp_path: Path, monkeypatch) -> None:
    """登録後 index.json に phash が保存されることを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)
    product_embedding_store_module._PRODUCT_EMBEDDING_STORE = ProductEmbeddingStore(
        file_path=root_dir / "embeddings.json"
    )
    monkeypatch.setattr(
        embedding_module,
        "compute_embedding_vector",
        lambda image_bytes, model_name, model_path, input_size: [0.0, 1.0],
    )

    record = store.create_image(
        sku="TEST-SKU",
        content_type="image/png",
        image_bytes=_sample_png_bytes(),
        note=None,
    )

    index_path = root_dir / INDEX_FILENAME
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["image_id"] == record.image_id
    assert payload["items"][0]["sku"] == "TEST-SKU"
    assert isinstance(payload["items"][0]["phash"], str)
    assert len(payload["items"][0]["phash"]) == 16
    product_embedding_store_module._PRODUCT_EMBEDDING_STORE = None


def test_reference_records_lazy_fill_missing_phash(tmp_path: Path, monkeypatch) -> None:
    """phash 欠損レコードが参照取得時に補完されることを確認する。"""
    root_dir = tmp_path / "product_images"
    store = ProductImageStore(root_dir=root_dir)
    product_embedding_store_module._PRODUCT_EMBEDDING_STORE = ProductEmbeddingStore(
        file_path=root_dir / "embeddings.json"
    )
    monkeypatch.setattr(
        embedding_module,
        "compute_embedding_vector",
        lambda image_bytes, model_name, model_path, input_size: [0.1, 0.2, 0.3],
    )
    created = store.create_image(
        sku="LAZY-001",
        content_type="image/png",
        image_bytes=_sample_png_bytes(),
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
    records = reloaded.list_reference_records(allowed_skus={"LAZY-001"})
    assert len(records) == 1
    assert records[0].image_id == created.image_id
    assert isinstance(records[0].phash, str)

    updated_payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert isinstance(updated_payload["items"][0]["phash"], str)
    product_embedding_store_module._PRODUCT_EMBEDDING_STORE = None


def test_normalize_sku_rejects_invalid_chars() -> None:
    """SKU 正規化で不正文字列を拒否することを確認する。"""
    with pytest.raises(ValueError):
        normalize_sku("../invalid")

    with pytest.raises(ValueError):
        normalize_sku(" ")
