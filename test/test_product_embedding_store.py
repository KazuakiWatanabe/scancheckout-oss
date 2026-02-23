"""商品 Embedding ストアの単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.models.product_embedding_store import ProductEmbeddingStore


def test_save_and_get_embedding(tmp_path: Path) -> None:
    """保存した Embedding を image_id で取得できることを確認する。"""
    store = ProductEmbeddingStore(file_path=tmp_path / "embeddings.json")
    store.save_embedding(
        image_id="img-1",
        vector=[0.1, 0.2, 0.3],
        model_name="mobilenetv3-small-224",
    )

    assert store.get_embedding("img-1") == [0.1, 0.2, 0.3]
    assert store.get_embedding("missing") is None
    metadata = store.metadata()
    assert metadata["model"] == "mobilenetv3-small-224"
    assert metadata["dim"] == 3
    assert metadata["count"] == 1


def test_get_embeddings_returns_requested_subset(tmp_path: Path) -> None:
    """複数保存時に要求 image_id のみ返すことを確認する。"""
    store = ProductEmbeddingStore(file_path=tmp_path / "embeddings.json")
    store.save_embedding(image_id="img-a", vector=[1.0, 0.0], model_name="m")
    store.save_embedding(image_id="img-b", vector=[0.0, 1.0], model_name="m")

    subset = store.get_embeddings(["img-b", "img-x"])
    assert subset == {"img-b": [0.0, 1.0]}


def test_corrupted_embeddings_json_raises_runtime_error(tmp_path: Path) -> None:
    """embeddings.json 破損時に RuntimeError を返すことを確認する。"""
    file_path = tmp_path / "embeddings.json"
    file_path.write_text("{broken-json", encoding="utf-8")

    store = ProductEmbeddingStore(file_path=file_path)
    with pytest.raises(RuntimeError) as exc_info:
        store.metadata()
    assert "embeddings.json の形式が不正です" in str(exc_info.value)
