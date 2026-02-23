"""アプリ設定値の読み込みモジュール。

本モジュールは推論関連の環境変数を集約し、以下を提供する。
- Embedding モデル設定（モデル名/パス/入力サイズ）
- Embedding Reject 閾値
- pHash ゲート設定（閾値/有効フラグ）

Note:
    - 設定未指定時は安全な既定値へフォールバックする。
    - 型変換に失敗した場合も例外を上げず既定値を使う。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InferSettings:
    """推論で利用する設定値。"""

    # Embedding モデル識別子。
    model_name: str
    # ONNX モデルファイルの絶対パス。
    model_path: Path
    # モデル入力サイズ（正方形）。
    input_size: int
    # Embedding の Reject 閾値。
    embed_threshold: float
    # pHash ゲート閾値。
    phash_threshold: float
    # pHash ゲート有効フラグ。
    phash_gate_enabled: bool


def _env(name: str, default: str) -> str:
    """環境変数を取得し、未設定時は default を返す。"""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip()
    return normalized if normalized else default


def _to_float(
    value: str, *, default: float, min_value: float, max_value: float
) -> float:
    """文字列を float に変換し、範囲外はクランプして返す。"""
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


def _to_int(value: str, *, default: int, min_value: int, max_value: int) -> int:
    """文字列を int に変換し、範囲外はクランプして返す。"""
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


def _to_bool(value: str, *, default: bool) -> bool:
    """文字列を bool に変換する。"""
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def get_infer_settings() -> InferSettings:
    """推論設定を環境変数から構築して返す。"""
    model_name = _env("INFER_MODEL_NAME", "mobilenetv3-small-224")
    model_path = Path(
        _env("INFER_MODEL_PATH", "assets/models/mobilenetv3_small_224.onnx")
    )
    input_size = _to_int(
        _env("INFER_MODEL_INPUT_SIZE", "224"),
        default=224,
        min_value=64,
        max_value=1024,
    )
    embed_threshold = _to_float(
        _env("INFER_EMBED_THRESHOLD", "0.65"),
        default=0.65,
        min_value=0.0,
        max_value=1.0,
    )
    phash_threshold = _to_float(
        _env("INFER_PHASH_THRESHOLD", "0.55"),
        default=0.55,
        min_value=0.0,
        max_value=1.0,
    )
    phash_gate_enabled = _to_bool(
        _env("INFER_PHASH_GATE_ENABLED", "true"),
        default=True,
    )
    return InferSettings(
        model_name=model_name,
        model_path=model_path,
        input_size=input_size,
        embed_threshold=embed_threshold,
        phash_threshold=phash_threshold,
        phash_gate_enabled=phash_gate_enabled,
    )
