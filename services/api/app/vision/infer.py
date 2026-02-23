"""Embedding 類似度ベースの推論モジュール。

本モジュールは、以下の推論ロジックを提供する。
- pHash による粗い Reject ゲート（任意）
- Embedding cosine 類似度で SKU 候補をランキング
- 閾値未満時の Reject（候補0件）

互換性のため、既存の pHash 推論 API も保持する。
- infer_with_phash
- infer_topk_candidates

Note:
    - DB/外部API には依存しない。
    - 入力に必要な参照データは routes 層から受け取る。
"""

from __future__ import annotations

import os
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
PHASH_MODEL_ID = "phash-reject-v1"
DEFAULT_PHASH_THRESHOLD = 0.55


@dataclass(frozen=True)
class CandidatePrediction:
    """推論候補1件を表す値オブジェクト。"""

    # 商品識別子（POS 連携で利用）。
    sku: str
    # 画面表示用の商品名。
    name: str
    # 0.0-1.0 の信頼度スコア。
    score: float


@dataclass(frozen=True)
class InferDecision:
    """推論結果全体を表す値オブジェクト。"""

    # 最終判定（threshold 以上なら True）。
    is_match: bool
    # best SKU のスコア。
    best_score: float
    # 判定に使った閾値。
    threshold: float
    # 候補配列。
    candidates: list[CandidatePrediction]
    # 返却するモデル識別子。
    model_id: str = ""


def get_phash_threshold() -> float:
    """環境変数から pHash 判定閾値を取得する。"""
    raw = os.getenv("INFER_PHASH_THRESHOLD")
    if raw is None or raw.strip() == "":
        return DEFAULT_PHASH_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PHASH_THRESHOLD
    return max(0.0, min(1.0, value))


def infer_with_phash(
    image_bytes: bytes,
    top_k: int = 3,
    theme_id: Optional[str] = None,
    allowed_skus: Optional[Sequence[str]] = None,
    reference_phashes_by_sku: Optional[dict[str, list[str]]] = None,
    threshold: Optional[float] = None,
) -> InferDecision:
    """pHash 類似度に基づいて候補 TopK と Reject 判定を返す。"""
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    threshold_value = (
        max(0.0, min(1.0, threshold))
        if threshold is not None
        else get_phash_threshold()
    )

    # theme_id 自体は呼び出しI/F互換のため受理する。
    _ = theme_id

    if allowed_skus is None:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=threshold_value,
            candidates=[],
            model_id=PHASH_MODEL_ID,
        )

    sorted_skus = sorted({sku for sku in allowed_skus if sku})
    if not sorted_skus:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=threshold_value,
            candidates=[],
            model_id=PHASH_MODEL_ID,
        )

    try:
        scan_phash = compute_phash_hex(image_bytes)
    except Exception:  # noqa: BLE001
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=threshold_value,
            candidates=[],
            model_id=PHASH_MODEL_ID,
        )

    phashes_map = reference_phashes_by_sku or {}
    sku_best_scores: list[tuple[str, float]] = []
    for sku in sorted_skus:
        phashes = phashes_map.get(sku) or []
        best_for_sku = 0.0
        has_valid_hash = False
        for ref_hash in phashes:
            if not ref_hash:
                continue
            try:
                distance = hamming_distance(scan_phash, ref_hash)
                score = score_from_hamming_distance(distance)
            except ValueError:
                continue
            has_valid_hash = True
            if score > best_for_sku:
                best_for_sku = score
        if has_valid_hash:
            sku_best_scores.append((sku, round(best_for_sku, 4)))

    if not sku_best_scores:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=threshold_value,
            candidates=[],
            model_id=PHASH_MODEL_ID,
        )

    ordered = sorted(sku_best_scores, key=lambda item: (-item[1], item[0]))
    best_score = ordered[0][1]
    is_match = best_score >= threshold_value
    if not is_match:
        return InferDecision(
            is_match=False,
            best_score=best_score,
            threshold=threshold_value,
            candidates=[],
            model_id=PHASH_MODEL_ID,
        )

    max_count = min(top_k, len(ordered))
    predictions: list[CandidatePrediction] = []
    for rank in range(max_count):
        sku, score = ordered[rank]
        predictions.append(CandidatePrediction(sku=sku, name=sku, score=score))

    return InferDecision(
        is_match=True,
        best_score=best_score,
        threshold=threshold_value,
        candidates=predictions,
        model_id=PHASH_MODEL_ID,
    )


def infer_topk_candidates(
    image_bytes: bytes,
    top_k: int = 3,
    theme_id: Optional[str] = None,
    allowed_skus: Optional[Sequence[str]] = None,
) -> list[CandidatePrediction]:
    """旧I/F互換のため候補一覧のみを返すラッパー。"""
    _ = image_bytes
    _ = theme_id
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if allowed_skus is None:
        return []
    sorted_skus = sorted({sku for sku in allowed_skus if sku})
    max_count = min(top_k, len(sorted_skus))
    predictions: list[CandidatePrediction] = []
    for rank in range(max_count):
        sku = sorted_skus[rank]
        raw_score = 0.95 - (rank * 0.12)
        score = round(max(0.01, min(0.99, raw_score)), 4)
        predictions.append(CandidatePrediction(sku=sku, name=sku, score=score))
    return predictions


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

    candidate_skus = sorted({sku for sku in allowed_skus if sku})
    if not candidate_skus:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=embed_threshold,
            candidates=[],
            model_id=embedding_module.MODEL_ID,
        )

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
