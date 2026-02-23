"""商品画像 Embedding の永続化ストア。

本モジュールは `storage/product_images/embeddings.json` を管理し、
画像ID（image_id）単位でベクトルを保存・取得する。

Note:
    - MVP は小規模前提の JSON 保存方式を採用する。
    - ファイル破損時は RuntimeError で明示的に通知する。
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Optional

EMBEDDINGS_VERSION = 1
EMBEDDINGS_FILENAME = "embeddings.json"


class ProductEmbeddingStore:
    """商品画像 Embedding を JSON で管理するストア。"""

    def __init__(self, file_path: Path) -> None:
        """ストアを初期化する。

        主要変数:
            file_path: embeddings.json の保存先。
        """
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self._file_path.exists():
            self._write_payload(
                {
                    "version": EMBEDDINGS_VERSION,
                    "model": "",
                    "dim": 0,
                    "items": {},
                }
            )

    def save_embedding(
        self,
        *,
        image_id: str,
        vector: list[float],
        model_name: str,
    ) -> None:
        """image_id に対応する Embedding を保存する。"""
        if not image_id:
            raise ValueError("image_id は必須です。")
        if not vector:
            raise ValueError("embedding vector が空です。")

        with self._lock:
            payload = self._read_payload()
            payload["model"] = model_name
            payload["dim"] = len(vector)
            items = payload.setdefault("items", {})
            items[image_id] = [float(value) for value in vector]
            self._write_payload(payload)

    def get_embedding(self, image_id: str) -> Optional[list[float]]:
        """image_id に対応する Embedding を返す。"""
        with self._lock:
            payload = self._read_payload()
            items = payload.get("items") or {}
            data = items.get(image_id)
            if data is None:
                return None
            return [float(value) for value in data]

    def get_embeddings(self, image_ids: list[str]) -> dict[str, list[float]]:
        """複数 image_id の Embedding をまとめて返す。"""
        wanted = {image_id for image_id in image_ids if image_id}
        if not wanted:
            return {}
        with self._lock:
            payload = self._read_payload()
            items = payload.get("items") or {}
            out: dict[str, list[float]] = {}
            for image_id in wanted:
                data = items.get(image_id)
                if data is None:
                    continue
                out[image_id] = [float(value) for value in data]
            return out

    def delete_embedding(self, image_id: str) -> bool:
        """image_id に対応する Embedding を削除する。"""
        with self._lock:
            payload = self._read_payload()
            items = payload.get("items") or {}
            existed = image_id in items
            if existed:
                items.pop(image_id, None)
                self._write_payload(payload)
            return existed

    def metadata(self) -> dict[str, object]:
        """保存中 Embedding のメタ情報を返す。"""
        with self._lock:
            payload = self._read_payload()
            return {
                "version": int(payload.get("version", EMBEDDINGS_VERSION)),
                "model": str(payload.get("model") or ""),
                "dim": int(payload.get("dim") or 0),
                "count": len(payload.get("items") or {}),
            }

    def _read_payload(self) -> dict[str, object]:
        """embeddings.json を読み込んで返す。"""
        try:
            raw = self._file_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"embeddings.json の形式が不正です: {self._file_path}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"embeddings.json の読み込みに失敗しました: {self._file_path}"
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"embeddings.json の形式が不正です: {self._file_path}")
        payload.setdefault("version", EMBEDDINGS_VERSION)
        payload.setdefault("model", "")
        payload.setdefault("dim", 0)
        payload.setdefault("items", {})
        return payload

    def _write_payload(self, payload: dict[str, object]) -> None:
        """embeddings.json を保存する。"""
        try:
            self._file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise RuntimeError(
                f"embeddings.json の保存に失敗しました: {self._file_path}"
            ) from exc


_PRODUCT_EMBEDDING_STORE: Optional[ProductEmbeddingStore] = None


def get_product_embedding_store() -> ProductEmbeddingStore:
    """Embedding ストアのシングルトンを返す。"""
    global _PRODUCT_EMBEDDING_STORE
    if _PRODUCT_EMBEDDING_STORE is None:
        _PRODUCT_EMBEDDING_STORE = ProductEmbeddingStore(
            file_path=Path("storage/product_images") / EMBEDDINGS_FILENAME
        )
    return _PRODUCT_EMBEDDING_STORE
