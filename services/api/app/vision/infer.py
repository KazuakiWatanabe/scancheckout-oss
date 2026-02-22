"""候補提示用のダミー推論モジュール。

本モジュールはモデル未導入段階の暫定ロジックとして、
候補 SKU 集合から安定順の TopK 候補を生成する。

Note:
    - DB や外部 API には依存しない。
    - 推論精度を目的とせず、UI/業務フロー検証用の出力を返す。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

MODEL_VERSION = "dummy-hash-v1"


@dataclass(frozen=True)
class CandidatePrediction:
    """推論候補1件を表す値オブジェクト。"""

    # 商品識別子（POS 連携で利用）。
    sku: str
    # 画面表示用の商品名。
    name: str
    # 0.0-1.0 の信頼度スコア。
    score: float


def infer_topk_candidates(
    image_bytes: bytes,
    top_k: int = 3,
    theme_id: Optional[str] = None,
    allowed_skus: Optional[Sequence[str]] = None,
) -> list[CandidatePrediction]:
    """候補 SKU 集合から安定順の TopK を生成する。

    主要変数:
        sorted_skus: 昇順ソート済みの候補 SKU 一覧。
        raw_score: 順位に応じて減衰させる暫定スコア。

    Note:
        - Phase 1 では画像比較を行わず、`allowed_skus` のみを利用する。
        - theme_id は呼び出しI/F互換のため受理する。
    """
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    # image_bytes/theme_id 自体は候補計算に使わない（I/F 互換維持）。
    _ = image_bytes
    _ = theme_id

    if allowed_skus is None:
        return []

    sorted_skus = sorted({sku for sku in allowed_skus if sku})
    if not sorted_skus:
        return []

    max_count = min(top_k, len(sorted_skus))

    predictions: list[CandidatePrediction] = []
    for rank in range(max_count):
        sku = sorted_skus[rank]
        raw_score = 0.95 - (rank * 0.12)
        score = round(max(0.01, min(0.99, raw_score)), 4)
        # 商品名は SKU をそのまま使う（Phase 1 の暫定仕様）。
        predictions.append(CandidatePrediction(sku=sku, name=sku, score=score))

    return predictions
