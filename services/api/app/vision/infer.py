"""Embedding 類似度ベースの推論モジュール。

本モジュールは、以下の推論ロジックを提供する。
- pHash による粗い Reject ゲート（任意）
- Embedding cosine 類似度で SKU 候補をランキング
- 閾値未満時の Reject（候補0件）

Note:
    - DB/外部API には依存しない。
    - 入力に必要な参照データは routes 層から受け取る。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
from app.vision import embedding as embedding_module
from app.vision.phash import (
    compute_phash_hex,
    hamming_distance,
    score_from_hamming_distance,
)

MODEL_VERSION = "embedding-onnx-v1"


@dataclass(frozen=True)
class CandidatePrediction:
    """推論候補1件を表す値オブジェクト。"""

    # 商品識別子（POS 連携で利用）。
    sku: str
    # 画面表示用の商品名。
    name: str
    # 0.0-1.0 の信頼度スコア（cosine 類似度）。
    score: float


@dataclass(frozen=True)
class InferDecision:
    """推論結果全体を表す値オブジェクト。"""

    # 最終判定（threshold 以上なら True）。
    is_match: bool
    # best SKU のスコア。
    best_score: float
    # Embedding 判定に使った閾値。
    threshold: float
    # 候補配列。
    candidates: list[CandidatePrediction]
    # 返却するモデル識別子。
    model_id: str


def infer_with_embedding(
    image_bytes: bytes,
    *,
    top_k: int,
    allowed_skus: Sequence[str],
    reference_embeddings_by_sku: dict[str, list[list[float]]],
    reference_phashes_by_sku: dict[str, list[str]],
    embed_threshold: float,
    phash_threshold: float,
    phash_gate_enabled: bool,
    model_name: str,
    model_path: Path,
    model_input_size: int,
) -> InferDecision:
    """Embedding 類似度に基づく推論を実行する。"""
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    # 候補集合を正規化し、空の場合は即 Reject。
    candidate_skus = sorted({sku for sku in allowed_skus if sku})
    if not candidate_skus:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=embed_threshold,
            candidates=[],
            model_id=embedding_module.MODEL_ID,
        )

    # pHash ゲート（高速な粗い判定）。
    if phash_gate_enabled:
        if not _is_phash_gate_passed(
            image_bytes=image_bytes,
            skus=candidate_skus,
            reference_phashes_by_sku=reference_phashes_by_sku,
            threshold=phash_threshold,
        ):
            return InferDecision(
                is_match=False,
                best_score=0.0,
                threshold=embed_threshold,
                candidates=[],
                model_id=embedding_module.MODEL_ID,
            )

    scan_vector = np.asarray(
        embedding_module.compute_embedding_vector(
            image_bytes,
            model_name=model_name,
            model_path=model_path,
            input_size=model_input_size,
        ),
        dtype=np.float32,
    )

    sku_scores: list[tuple[str, float]] = []
    for sku in candidate_skus:
        reference_vectors = reference_embeddings_by_sku.get(sku) or []
        best_for_sku = _best_similarity(scan_vector, reference_vectors)
        if best_for_sku is None:
            continue
        sku_scores.append((sku, round(best_for_sku, 4)))

    if not sku_scores:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=embed_threshold,
            candidates=[],
            model_id=embedding_module.MODEL_ID,
        )

    ordered = sorted(sku_scores, key=lambda item: (-item[1], item[0]))
    best_score = ordered[0][1]
    if best_score < embed_threshold:
        return InferDecision(
            is_match=False,
            best_score=best_score,
            threshold=embed_threshold,
            candidates=[],
            model_id=embedding_module.MODEL_ID,
        )

    max_count = min(top_k, len(ordered))
    candidates: list[CandidatePrediction] = []
    for idx in range(max_count):
        sku, score = ordered[idx]
        candidates.append(CandidatePrediction(sku=sku, name=sku, score=score))

    return InferDecision(
        is_match=True,
        best_score=best_score,
        threshold=embed_threshold,
        candidates=candidates,
        model_id=embedding_module.MODEL_ID,
    )


def _is_phash_gate_passed(
    *,
    image_bytes: bytes,
    skus: list[str],
    reference_phashes_by_sku: dict[str, list[str]],
    threshold: float,
) -> bool:
    """pHash 粗判定を通過するか返す。"""
    try:
        scan_hash = compute_phash_hex(image_bytes)
    except Exception:  # noqa: BLE001
        return False

    best_score = 0.0
    for sku in skus:
        for ref_hash in reference_phashes_by_sku.get(sku) or []:
            if not ref_hash:
                continue
            try:
                distance = hamming_distance(scan_hash, ref_hash)
            except ValueError:
                continue
            score = score_from_hamming_distance(distance)
            if score > best_score:
                best_score = score
    return best_score >= threshold


def _best_similarity(
    scan_vector: np.ndarray,
    reference_vectors: list[list[float]],
) -> Optional[float]:
    """1 SKU 内で最も高い cosine 類似度を返す。"""
    best: Optional[float] = None
    for ref in reference_vectors:
        ref_vector = np.asarray(ref, dtype=np.float32)
        if ref_vector.ndim != 1 or ref_vector.shape[0] != scan_vector.shape[0]:
            continue
        score = embedding_module.cosine_similarity(scan_vector, ref_vector)
        if best is None or score > best:
            best = score
    return best
