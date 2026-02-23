"""候補提示用のダミー推論モジュール。

本モジュールは MVP 向けに、以下を提供する。
- 商品画像マスターの pHash と撮影画像 pHash の類似度比較
- TopK 候補生成
- 閾値未満時の Reject（該当なし）判定

Note:
    - DB や外部 API には依存しない。
    - `INFER_PHASH_THRESHOLD` で reject 閾値を上書きできる。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Sequence

from app.vision.phash import (
    compute_phash_hex,
    hamming_distance,
    score_from_hamming_distance,
)

MODEL_VERSION = "phash-reject-v1"
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

    # threshold を満たす候補が存在するかどうか。
    is_match: bool
    # 全候補中の最高スコア（候補0件時は 0.0）。
    best_score: float
    # 判定に使った閾値。
    threshold: float
    # 返却対象の候補一覧。
    candidates: list[CandidatePrediction]


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
    """pHash 類似度に基づいて候補 TopK と Reject 判定を返す。

    主要変数:
        sorted_skus: 推論対象 SKU を正規化・昇順化した配列。
        best_score: 全SKUの中で最も高い類似スコア。
        threshold_value: reject 判定に使う閾値。

    Note:
        - `best_score < threshold` の場合は candidates を空で返す。
        - `reference_phashes_by_sku` に pHash が無い SKU は評価対象外とする。
    """
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
        )

    sorted_skus = sorted({sku for sku in allowed_skus if sku})
    if not sorted_skus:
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=threshold_value,
            candidates=[],
        )

    try:
        scan_phash = compute_phash_hex(image_bytes)
    except Exception:  # noqa: BLE001
        return InferDecision(
            is_match=False,
            best_score=0.0,
            threshold=threshold_value,
            candidates=[],
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
        )

    max_count = min(top_k, len(ordered))
    predictions: list[CandidatePrediction] = []
    for rank in range(max_count):
        sku, score = ordered[rank]
        # 商品名は SKU をそのまま使う（Phase 1 の暫定仕様）。
        predictions.append(CandidatePrediction(sku=sku, name=sku, score=score))

    return InferDecision(
        is_match=True,
        best_score=best_score,
        threshold=threshold_value,
        candidates=predictions,
    )


def infer_topk_candidates(
    image_bytes: bytes,
    top_k: int = 3,
    theme_id: Optional[str] = None,
    allowed_skus: Optional[Sequence[str]] = None,
) -> list[CandidatePrediction]:
    """旧I/F互換のため候補一覧のみを返すラッパー。"""
    # pHash 参照が渡されない旧経路では、従来どおり候補SKUを安定順で返す。
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
