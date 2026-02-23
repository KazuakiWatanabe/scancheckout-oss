"""Embedding 推論のランキング/Reject テスト。"""

from __future__ import annotations

from io import BytesIO

from app.vision import embedding as embedding_module
from app.vision.infer import infer_with_embedding
from app.vision.phash import compute_phash_hex
from PIL import Image, ImageDraw


def _image_bytes(kind: str) -> bytes:
    """比較用の画像バイト列を生成する。"""
    image = Image.new("RGB", (64, 64), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    if kind == "a":
        draw.rectangle((8, 8, 30, 30), fill=(20, 20, 20))
        draw.rectangle((35, 35, 56, 56), fill=(180, 50, 50))
    elif kind == "b":
        draw.ellipse((8, 8, 30, 30), fill=(20, 20, 20))
        draw.line((0, 63, 63, 0), fill=(10, 10, 10), width=4)
    else:
        raise ValueError(f"unknown kind: {kind}")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_embedding_infer_returns_top1_for_closest_sku(monkeypatch) -> None:
    """近い参照 Embedding がある SKU が top1 になることを確認する。"""
    monkeypatch.setattr(
        embedding_module,
        "compute_embedding_vector",
        lambda image_bytes, model_name, model_path, input_size: [1.0, 0.0],
    )

    result = infer_with_embedding(
        _image_bytes("a"),
        top_k=2,
        allowed_skus=["SKU-A", "SKU-B"],
        reference_embeddings_by_sku={
            "SKU-A": [[1.0, 0.0]],
            "SKU-B": [[0.0, 1.0]],
        },
        reference_phashes_by_sku={},
        embed_threshold=0.65,
        phash_threshold=0.55,
        phash_gate_enabled=False,
        model_name="dummy",
        model_path="dummy.onnx",
        model_input_size=224,
    )

    assert result.is_match is True
    assert result.candidates[0].sku == "SKU-A"
    assert result.best_score == 1.0


def test_embedding_infer_rejects_when_best_score_below_threshold(monkeypatch) -> None:
    """best_score が閾値未満なら candidates が空になることを確認する。"""
    monkeypatch.setattr(
        embedding_module,
        "compute_embedding_vector",
        lambda image_bytes, model_name, model_path, input_size: [1.0, 0.0],
    )

    result = infer_with_embedding(
        _image_bytes("a"),
        top_k=2,
        allowed_skus=["SKU-A"],
        reference_embeddings_by_sku={"SKU-A": [[0.1, 0.99]]},
        reference_phashes_by_sku={},
        embed_threshold=0.95,
        phash_threshold=0.55,
        phash_gate_enabled=False,
        model_name="dummy",
        model_path="dummy.onnx",
        model_input_size=224,
    )

    assert result.is_match is False
    assert result.candidates == []
    assert result.best_score < 0.95


def test_phash_gate_rejects_before_embedding(monkeypatch) -> None:
    """pHash ゲート未通過時は Embedding 候補が返らないことを確認する。"""
    called = {"count": 0}

    def _fake_embedding(
        image_bytes, model_name, model_path, input_size
    ):  # noqa: ANN001
        called["count"] += 1
        return [1.0, 0.0]

    monkeypatch.setattr(embedding_module, "compute_embedding_vector", _fake_embedding)

    scan = _image_bytes("a")
    ref = _image_bytes("b")
    result = infer_with_embedding(
        scan,
        top_k=1,
        allowed_skus=["SKU-A"],
        reference_embeddings_by_sku={"SKU-A": [[1.0, 0.0]]},
        reference_phashes_by_sku={"SKU-A": [compute_phash_hex(ref)]},
        embed_threshold=0.65,
        phash_threshold=0.99,
        phash_gate_enabled=True,
        model_name="dummy",
        model_path="dummy.onnx",
        model_input_size=224,
    )

    assert result.is_match is False
    assert result.candidates == []
    # pHash で reject されるため Embedding 推論は実行されない。
    assert called["count"] == 0
