"""pHash 推論の reject 判定テスト。

検証対象:
- 近い画像がある場合に top1 が正しく返ること
- 閾値により reject 判定が変化すること
- 参照 pHash 欠損時に 500 にならず候補空で返ること
"""

from __future__ import annotations

from io import BytesIO

from app.vision.infer import infer_with_phash
from app.vision.phash import compute_phash_hex
from PIL import Image, ImageDraw


def _image_bytes(kind: str) -> bytes:
    """比較用の画像バイト列を生成する。"""
    image = Image.new("RGB", (64, 64), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)

    if kind == "a":
        draw.rectangle((8, 8, 30, 30), fill=(20, 20, 20))
        draw.rectangle((35, 35, 56, 56), fill=(180, 50, 50))
    elif kind == "b":
        draw.ellipse((8, 8, 30, 30), fill=(20, 20, 20))
        draw.line((0, 63, 63, 0), fill=(10, 10, 10), width=4)
    else:
        raise ValueError(f"unknown kind: {kind}")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _flip_hash_bits(phash_hex: str, *, count: int) -> str:
    """先頭から指定ビット数だけ反転した pHash を返す。"""
    raw = int(phash_hex, 16)
    for idx in range(max(0, count)):
        bit_pos = 63 - idx
        raw ^= 1 << bit_pos
    return f"{raw:016x}"


def test_infer_accepts_and_returns_top1_when_close_reference_exists() -> None:
    """同一に近い参照がある場合に is_match=true で top1 が返ることを確認する。"""
    scan = _image_bytes("a")
    ref_a = compute_phash_hex(scan)
    ref_b = compute_phash_hex(_image_bytes("b"))

    result = infer_with_phash(
        image_bytes=scan,
        top_k=2,
        allowed_skus=["SKU-A", "SKU-B"],
        reference_phashes_by_sku={
            "SKU-A": [ref_a],
            "SKU-B": [ref_b],
        },
        threshold=0.55,
    )

    assert result.is_match is True
    assert result.best_score == 1.0
    assert len(result.candidates) == 2
    assert result.candidates[0].sku == "SKU-A"


def test_infer_reject_changes_with_threshold() -> None:
    """threshold を変えると reject 判定が変わることを確認する。"""
    scan = _image_bytes("a")
    scan_hash = compute_phash_hex(scan)
    # 距離32相当（score=0.5）になるようビットを反転する。
    far_hash = _flip_hash_bits(scan_hash, count=32)

    rejected = infer_with_phash(
        image_bytes=scan,
        top_k=1,
        allowed_skus=["SKU-A"],
        reference_phashes_by_sku={"SKU-A": [far_hash]},
        threshold=0.6,
    )
    assert rejected.is_match is False
    assert rejected.best_score == 0.5
    assert rejected.candidates == []

    accepted = infer_with_phash(
        image_bytes=scan,
        top_k=1,
        allowed_skus=["SKU-A"],
        reference_phashes_by_sku={"SKU-A": [far_hash]},
        threshold=0.4,
    )
    assert accepted.is_match is True
    assert accepted.best_score == 0.5
    assert len(accepted.candidates) == 1
    assert accepted.candidates[0].sku == "SKU-A"


def test_infer_returns_empty_when_reference_phash_missing() -> None:
    """参照 pHash が無い場合でも例外を出さず候補空で返すことを確認する。"""
    result = infer_with_phash(
        image_bytes=_image_bytes("a"),
        top_k=3,
        allowed_skus=["SKU-A"],
        reference_phashes_by_sku={"SKU-A": []},
        threshold=0.55,
    )

    assert result.is_match is False
    assert result.best_score == 0.0
    assert result.candidates == []
