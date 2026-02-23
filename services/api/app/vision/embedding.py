"""ONNX Embedding 推論ユーティリティ。

本モジュールは商品画像の埋め込みベクトル計算を担当する。
- ONNX Runtime でモデル推論
- 前処理（RGB/224x224/正規化）
- 出力ベクトルの L2 正規化

Note:
    - モデル未配置や onnxruntime 未導入時は明示的な例外を返す。
    - routes/models 層は本モジュールの公開関数のみを利用する。
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - 依存の有無で分岐
    ort = None

MODEL_ID = "embedding-onnx-v1"

# ImageNet 系モデルで一般的な正規化値。
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class EmbeddingModelError(RuntimeError):
    """Embedding モデル関連のエラー。"""


@dataclass(frozen=True)
class EmbeddingModelSpec:
    """Embedding モデルの指定情報。"""

    # モデル識別名（ログ/保存用）。
    model_name: str
    # ONNX モデルのファイルパス。
    model_path: Path
    # モデル入力サイズ（正方形）。
    input_size: int


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    """ベクトルを L2 正規化して返す。"""
    if vector.ndim != 1:
        raise ValueError("vector must be 1-dimensional")
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        return vector.astype(np.float32)
    return (vector / norm).astype(np.float32)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """2つの正規化ベクトルの cosine 類似度を返す。"""
    if vec_a.ndim != 1 or vec_b.ndim != 1:
        raise ValueError("cosine_similarity expects 1-dimensional vectors")
    if vec_a.shape[0] != vec_b.shape[0]:
        raise ValueError("vector dimension mismatch")
    score = float(np.dot(vec_a, vec_b))
    return max(0.0, min(1.0, score))


def compute_embedding_vector(
    image_bytes: bytes,
    *,
    model_name: str,
    model_path: Path,
    input_size: int = 224,
) -> list[float]:
    """画像バイト列から Embedding ベクトルを計算して返す。"""
    if not image_bytes:
        raise EmbeddingModelError("embedding 対象の image_bytes が空です。")

    spec = EmbeddingModelSpec(
        model_name=model_name,
        model_path=model_path,
        input_size=input_size,
    )
    session = _get_cached_session(spec.model_path)
    input_tensor = _preprocess_image(
        image_bytes=image_bytes,
        input_size=spec.input_size,
    )
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    if not outputs:
        raise EmbeddingModelError("ONNX 推論結果が空です。")
    raw = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
    normalized = normalize_vector(raw)
    return normalized.tolist()


@lru_cache(maxsize=2)
def _get_cached_session(model_path: Path):
    """ONNX セッションをキャッシュ付きで取得する。"""
    if ort is None:
        raise EmbeddingModelError(
            "onnxruntime がインストールされていません。"
            " `pip install onnxruntime` を実行してください。"
        )
    resolved = model_path.resolve()
    if not resolved.exists():
        raise EmbeddingModelError(
            f"ONNX モデルが見つかりません: {resolved}. "
            "assets/models にモデルを配置してください。"
        )
    try:
        return ort.InferenceSession(
            str(resolved),
            providers=["CPUExecutionProvider"],
        )
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingModelError(f"ONNX モデル読み込みに失敗しました: {exc}") from exc


def _preprocess_image(*, image_bytes: bytes, input_size: int) -> np.ndarray:
    """モデル入力形式に画像を前処理して返す。"""
    if input_size <= 0:
        raise EmbeddingModelError(f"input_size が不正です: {input_size}")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB").resize(
                (input_size, input_size),
                Image.Resampling.BILINEAR,
            )
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingModelError(f"画像の前処理に失敗しました: {exc}") from exc

    array = np.asarray(rgb, dtype=np.float32) / 255.0
    normalized = (array - _MEAN) / _STD
    chw = np.transpose(normalized, (2, 0, 1))
    batched = np.expand_dims(chw, axis=0)
    return batched.astype(np.float32)
