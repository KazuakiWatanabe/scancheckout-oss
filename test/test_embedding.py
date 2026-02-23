"""Embedding ユーティリティの単体テスト。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from app.vision import embedding as embedding_module
from PIL import Image


def _sample_png_bytes() -> bytes:
    """テスト用 PNG 画像を返す。"""
    image = Image.new("RGB", (8, 8), color=(120, 80, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_normalize_vector_returns_unit_norm() -> None:
    """L2 正規化後のノルムが 1.0 になることを確認する。"""
    vector = np.asarray([3.0, 4.0], dtype=np.float32)
    normalized = embedding_module.normalize_vector(vector)
    assert np.isclose(float(np.linalg.norm(normalized)), 1.0)


def test_cosine_similarity_works_for_normalized_vectors() -> None:
    """cosine 類似度が期待どおりに計算されることを確認する。"""
    vec_a = np.asarray([1.0, 0.0], dtype=np.float32)
    vec_b = np.asarray([1.0, 0.0], dtype=np.float32)
    vec_c = np.asarray([0.0, 1.0], dtype=np.float32)
    assert embedding_module.cosine_similarity(vec_a, vec_b) == 1.0
    assert embedding_module.cosine_similarity(vec_a, vec_c) == 0.0


def test_compute_embedding_vector_raises_clear_error_when_model_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """モデルファイル未配置時に分かりやすいエラーを返すことを確認する。"""

    class _FakeOrt:
        """onnxruntime 代替のダミーオブジェクト。"""

        @staticmethod
        def InferenceSession(*args, **kwargs):  # noqa: D401, ANN002, ANN003
            raise AssertionError("このテストでは呼ばれない想定")

    monkeypatch.setattr(embedding_module, "ort", _FakeOrt)
    embedding_module._get_cached_session.cache_clear()

    missing_path = tmp_path / "missing.onnx"
    try:
        embedding_module.compute_embedding_vector(
            _sample_png_bytes(),
            model_name="dummy",
            model_path=missing_path,
            input_size=224,
        )
    except embedding_module.EmbeddingModelError as exc:
        message = str(exc)
        assert "ONNX モデルが見つかりません" in message
        assert str(missing_path.resolve()) in message
    else:
        raise AssertionError("EmbeddingModelError が発生しませんでした。")
