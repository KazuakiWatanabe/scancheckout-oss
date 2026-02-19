"""候補提示用のダミー推論モジュール。

本モジュールはモデル未導入段階の暫定ロジックとして、
画像バイト列から再現性のある TopK 候補を生成する。

Note:
    - DB や外部 API には依存しない。
    - 推論精度を目的とせず、UI/業務フロー検証用の出力を返す。
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

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


def infer_topk_candidates(image_bytes: bytes, top_k: int = 3) -> list[CandidatePrediction]:
    """画像バイト列から候補 TopK を生成する。

    主要変数:
        digest: 画像バイト列のハッシュ値。
        start_index: 候補カタログの開始オフセット。
        score_noise: ハッシュ由来の微小ノイズ。
    """
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    # MVP での固定候補カタログ。
    catalog = [
        ("TEST-SVC", "Demo Service SKU"),
        ("TEST-SKU", "Demo Product TEST"),
        ("BREAD-001", "Croissant"),
        ("BREAD-002", "Baguette"),
        ("CAKE-001", "Cheese Cake"),
    ]
    if not image_bytes:
        image_bytes = b"empty-image"

    digest = sha256(image_bytes).digest()
    start_index = digest[0] % len(catalog)
    max_count = min(top_k, len(catalog))

    predictions: list[CandidatePrediction] = []
    for rank in range(max_count):
        idx = (start_index + rank) % len(catalog)
        sku, name = catalog[idx]
        score_noise = digest[(rank + 1) % len(digest)] / 2550.0
        raw_score = 0.95 - (rank * 0.12) - score_noise
        score = round(max(0.01, min(0.99, raw_score)), 4)
        predictions.append(CandidatePrediction(sku=sku, name=name, score=score))

    return predictions
