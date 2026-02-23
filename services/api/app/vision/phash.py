"""pHash（知覚ハッシュ）計算と類似度計算ユーティリティ。

本モジュールは画像同士の近さを測るために、以下を提供する。
- 画像バイト列から 64bit pHash（16進文字列）を生成
- pHash 同士のハミング距離を計算
- ハミング距離を 0.0-1.0 のスコアへ正規化

Note:
    - `imagehash` が利用可能な場合は `imagehash.phash` を優先利用する。
    - `imagehash` 未導入環境では、Pillow と純Python DCT で同等の計算を行う。
"""

from __future__ import annotations

import io
import math
from functools import lru_cache
from typing import Optional

from PIL import Image

try:
    import imagehash
except ImportError:  # pragma: no cover - 環境依存分岐
    imagehash = None

PHASH_BITS = 64
PHASH_HEX_LENGTH = 16
_DEFAULT_HASH_SIZE = 8
_DEFAULT_HIGH_FREQ_FACTOR = 4


def normalize_phash_hex(value: str) -> str:
    """pHash 16進文字列を正規化して返す。"""
    normalized = value.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    if not normalized:
        raise ValueError("phash が空です。")
    try:
        as_int = int(normalized, 16)
    except ValueError as exc:
        raise ValueError(f"phash が16進文字列ではありません: {value}") from exc
    return f"{as_int:0{PHASH_HEX_LENGTH}x}"[-PHASH_HEX_LENGTH:]


def hamming_distance(phash_a: str, phash_b: str) -> int:
    """2つの pHash のハミング距離を返す。"""
    norm_a = normalize_phash_hex(phash_a)
    norm_b = normalize_phash_hex(phash_b)
    xor_value = int(norm_a, 16) ^ int(norm_b, 16)
    return xor_value.bit_count()


def score_from_hamming_distance(distance: int, bits: int = PHASH_BITS) -> float:
    """ハミング距離を 0.0-1.0 の類似スコアへ変換する。"""
    if bits <= 0:
        raise ValueError("bits must be > 0")
    clamped = max(0, min(bits, int(distance)))
    return max(0.0, min(1.0, 1.0 - (clamped / float(bits))))


def compute_phash_hex(
    image_bytes: bytes,
    *,
    hash_size: int = _DEFAULT_HASH_SIZE,
) -> str:
    """画像バイト列から 64bit pHash（16進文字列）を返す。"""
    if not image_bytes:
        raise ValueError("image_bytes が空です。")

    if imagehash is not None:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return normalize_phash_hex(str(imagehash.phash(image, hash_size=hash_size)))

    # Fallback: imagehash が無い環境では純Python DCTで pHash を求める。
    return _compute_phash_hex_fallback(
        image_bytes=image_bytes,
        hash_size=hash_size,
        high_freq_factor=_DEFAULT_HIGH_FREQ_FACTOR,
    )


def _compute_phash_hex_fallback(
    *,
    image_bytes: bytes,
    hash_size: int,
    high_freq_factor: int,
) -> str:
    """imagehash 非依存で pHash を計算する内部実装。"""
    if hash_size <= 0:
        raise ValueError("hash_size must be > 0")
    if high_freq_factor <= 0:
        raise ValueError("high_freq_factor must be > 0")

    size = hash_size * high_freq_factor
    pixels = _load_luma_pixels(image_bytes=image_bytes, size=size)
    dct = _dct_2d(pixels)

    low_freq: list[list[float]] = [
        [dct[row][col] for col in range(hash_size)] for row in range(hash_size)
    ]
    values_for_median = [v for row in low_freq for v in row][1:]
    median_value = _median(values_for_median)
    bits = [1 if value > median_value else 0 for row in low_freq for value in row]

    as_int = 0
    for bit in bits:
        as_int = (as_int << 1) | bit
    return normalize_phash_hex(f"{as_int:0{PHASH_HEX_LENGTH}x}")


def _load_luma_pixels(*, image_bytes: bytes, size: int) -> list[list[float]]:
    """画像をグレースケールへ変換し、2次元ピクセル配列を返す。"""
    with Image.open(io.BytesIO(image_bytes)) as image:
        gray = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
        flat = list(gray.getdata())

    rows: list[list[float]] = []
    for row_idx in range(size):
        start = row_idx * size
        rows.append([float(v) for v in flat[start : start + size]])
    return rows


@lru_cache(maxsize=8)
def _cos_table(size: int) -> list[list[float]]:
    """DCT 計算で使う余弦テーブルを返す。"""
    table: list[list[float]] = []
    for u in range(size):
        row = []
        for x in range(size):
            row.append(math.cos(((2 * x + 1) * u * math.pi) / (2 * size)))
        table.append(row)
    return table


def _dct_2d(matrix: list[list[float]]) -> list[list[float]]:
    """2次元配列へ DCT-II を適用する。"""
    size = len(matrix)
    cosines = _cos_table(size)
    result = [[0.0 for _ in range(size)] for _ in range(size)]

    for u in range(size):
        alpha_u = math.sqrt(1 / size) if u == 0 else math.sqrt(2 / size)
        for v in range(size):
            alpha_v = math.sqrt(1 / size) if v == 0 else math.sqrt(2 / size)
            acc = 0.0
            for x in range(size):
                cos_ux = cosines[u][x]
                row = matrix[x]
                for y in range(size):
                    acc += row[y] * cos_ux * cosines[v][y]
            result[u][v] = alpha_u * alpha_v * acc
    return result


def _median(values: list[float]) -> float:
    """数値配列の中央値を返す。"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0
