"""pHash（知覚ハッシュ）計算ユーティリティ。

本モジュールは、画像類似の粗い判定（Reject ゲート）で使う
64bit pHash の計算と比較を提供する。

Note:
    - `imagehash` が利用可能な場合はそれを優先利用する。
    - 未導入時は純Python DCT 実装へフォールバックする。
"""

from __future__ import annotations

import io
import math
from functools import lru_cache

from PIL import Image

try:
    import imagehash
except ImportError:  # pragma: no cover - 依存の有無で分岐
    imagehash = None

PHASH_BITS = 64
PHASH_HEX_LENGTH = 16
_DEFAULT_HASH_SIZE = 8
_DEFAULT_HIGH_FREQ_FACTOR = 4


def normalize_phash_hex(value: str) -> str:
    """pHash の16進文字列を正規化して返す。"""
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


def compute_phash_hex(image_bytes: bytes) -> str:
    """画像バイト列から 64bit pHash（16進文字列）を返す。"""
    if not image_bytes:
        raise ValueError("image_bytes が空です。")

    if imagehash is not None:
        with Image.open(io.BytesIO(image_bytes)) as image:
            hashed = imagehash.phash(image, hash_size=_DEFAULT_HASH_SIZE)
            return normalize_phash_hex(str(hashed))

    return _compute_phash_fallback(image_bytes=image_bytes)


def hamming_distance(phash_a: str, phash_b: str) -> int:
    """2つの pHash のハミング距離を返す。"""
    a = int(normalize_phash_hex(phash_a), 16)
    b = int(normalize_phash_hex(phash_b), 16)
    return (a ^ b).bit_count()


def score_from_hamming_distance(distance: int) -> float:
    """ハミング距離を 0.0-1.0 のスコアへ変換する。"""
    d = max(0, min(PHASH_BITS, int(distance)))
    return max(0.0, min(1.0, 1.0 - (d / PHASH_BITS)))


def _compute_phash_fallback(*, image_bytes: bytes) -> str:
    """imagehash 未導入時に使う pHash 計算。"""
    hash_size = _DEFAULT_HASH_SIZE
    size = hash_size * _DEFAULT_HIGH_FREQ_FACTOR
    pixels = _load_luma_pixels(image_bytes=image_bytes, size=size)
    dct = _dct_2d(pixels)

    low_freq = [[dct[row][col] for col in range(hash_size)] for row in range(hash_size)]
    values = [value for row in low_freq for value in row][1:]
    median_value = _median(values)
    bits = [1 if value > median_value else 0 for row in low_freq for value in row]

    as_int = 0
    for bit in bits:
        as_int = (as_int << 1) | bit
    return normalize_phash_hex(f"{as_int:0{PHASH_HEX_LENGTH}x}")


def _load_luma_pixels(*, image_bytes: bytes, size: int) -> list[list[float]]:
    """画像をグレースケール化して2次元配列に変換する。"""
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
    """DCT 計算に使う余弦テーブルを返す。"""
    table: list[list[float]] = []
    for u in range(size):
        row = []
        for x in range(size):
            row.append(math.cos(((2 * x + 1) * u * math.pi) / (2 * size)))
        table.append(row)
    return table


def _dct_2d(matrix: list[list[float]]) -> list[list[float]]:
    """2次元 DCT-II を計算する。"""
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
