"""pHash ユーティリティの単体テスト。

検証対象:
- 同一画像の pHash 安定性
- ハミング距離とスコア変換
- 16進文字列正規化
"""

from __future__ import annotations

from io import BytesIO

from app.vision.phash import (
    compute_phash_hex,
    hamming_distance,
    normalize_phash_hex,
    score_from_hamming_distance,
)
from PIL import Image, ImageDraw


def _sample_pattern_bytes() -> bytes:
    """テスト用のパターン画像バイト列を返す。"""
    image = Image.new("RGB", (64, 64), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 30, 30), fill=(30, 30, 30))
    draw.rectangle((34, 34, 56, 56), fill=(180, 50, 50))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_compute_phash_is_stable_for_same_image() -> None:
    """同一画像から同一 pHash が計算されることを確認する。"""
    image_bytes = _sample_pattern_bytes()

    hash_a = compute_phash_hex(image_bytes)
    hash_b = compute_phash_hex(image_bytes)

    assert hash_a == hash_b
    assert len(hash_a) == 16


def test_hamming_distance_and_score_conversion() -> None:
    """距離計算とスコア変換が期待どおりであることを確認する。"""
    assert hamming_distance("0000000000000000", "ffffffffffffffff") == 64
    assert score_from_hamming_distance(64) == 0.0
    assert score_from_hamming_distance(32) == 0.5
    assert score_from_hamming_distance(0) == 1.0


def test_normalize_phash_hex_accepts_prefixed_value() -> None:
    """0x 接頭辞付き pHash を正規化できることを確認する。"""
    normalized = normalize_phash_hex("0xAbCd")
    assert normalized.endswith("abcd")
    assert len(normalized) == 16
