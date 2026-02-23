"""商品画像マスターの永続化ストア。

本モジュールは Phase 1（MVP）向けに、以下を担当する。
- 商品画像ファイルのローカル保存
- 画像メタデータ（index.json）の管理
- SKU 単位の検索、image_id 単位の取得/削除

Note:
    - 商品画像ごとの pHash を index.json に保持する。
    - 画像は `storage/product_images/<sku>/<image_id>.<ext>` へ保存する。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.vision.phash import compute_phash_hex

INDEX_VERSION = 1
INDEX_FILENAME = "index.json"

CONTENT_TYPE_TO_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# SKU はパス構成要素に使うため、許容文字を明示的に制限する。
SKU_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class ProductImageRecord:
    """商品画像メタデータの1件レコード。

    主要変数:
        image_id: 画像識別子（UUID 文字列）。
        sku: 商品識別子。
        filename: 保存ファイル名（`<image_id>.<ext>`）。
        content_type: MIME タイプ。
        created_at: 登録時刻（UTC）。
        note: 補足メモ（任意）。
        phash: 画像の知覚ハッシュ（16進文字列、計算不可時は None）。
    """

    image_id: str
    sku: str
    filename: str
    content_type: str
    created_at: datetime
    note: Optional[str]
    phash: Optional[str]


def normalize_sku(value: str) -> str:
    """SKU を正規化して返す。

    Note:
        - 空文字や禁止文字を含む場合は ValueError を送出する。
        - ディレクトリトラバーサル対策として `/` や `..` は拒否する。
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError("sku は必須です。")
    if not SKU_PATTERN.fullmatch(normalized):
        raise ValueError(
            "sku は英数字・ハイフン・アンダースコア・ドットのみ利用できます。"
        )
    return normalized


class ProductImageStore:
    """商品画像マスターを JSON + ファイルで管理するストア。"""

    def __init__(self, root_dir: Path) -> None:
        """ストアを初期化する。

        主要変数:
            root_dir: `index.json` と SKU ディレクトリを保持するルート。
            index_path: メタデータ JSON の保存先パス。
        """
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._root_dir / INDEX_FILENAME
        self._lock = Lock()
        self._records_by_id: dict[str, ProductImageRecord] = {}
        self._load_index()

    def create_image(
        self,
        *,
        sku: str,
        content_type: str,
        image_bytes: bytes,
        note: Optional[str],
    ) -> ProductImageRecord:
        """商品画像を保存し、メタデータを追加する。"""
        normalized_sku = normalize_sku(sku)
        suffix = CONTENT_TYPE_TO_SUFFIX.get(content_type)
        if not suffix:
            raise ValueError(f"unsupported content_type: {content_type}")

        image_id = str(uuid4())
        filename = f"{image_id}{suffix}"
        sku_dir = self._root_dir / normalized_sku
        sku_dir.mkdir(parents=True, exist_ok=True)
        image_path = sku_dir / filename
        image_path.write_bytes(image_bytes)

        record = ProductImageRecord(
            image_id=image_id,
            sku=normalized_sku,
            filename=filename,
            content_type=content_type,
            created_at=datetime.now(timezone.utc),
            note=note.strip() if note and note.strip() else None,
            phash=self._compute_phash_safe(image_bytes=image_bytes),
        )
        with self._lock:
            self._records_by_id[record.image_id] = record
            self._save_index()
        return record

    def list_images(self, *, sku: Optional[str] = None) -> list[ProductImageRecord]:
        """画像メタデータ一覧を返す。"""
        with self._lock:
            records = list(self._records_by_id.values())

        if sku is None:
            return sorted(records, key=lambda item: item.created_at, reverse=True)

        normalized_sku = normalize_sku(sku)
        filtered = [record for record in records if record.sku == normalized_sku]
        return sorted(filtered, key=lambda item: item.created_at, reverse=True)

    def get_image(self, image_id: str) -> Optional[ProductImageRecord]:
        """image_id で画像メタデータを取得する。"""
        with self._lock:
            return self._records_by_id.get(image_id)

    def has_sku(self, sku: str) -> bool:
        """指定 SKU が1件以上登録されているかを返す。"""
        normalized_sku = normalize_sku(sku)
        with self._lock:
            return any(
                record.sku == normalized_sku for record in self._records_by_id.values()
            )

    def get_image_path(self, image_id: str) -> Optional[Path]:
        """image_id に対応する画像ファイルパスを返す。"""
        record = self.get_image(image_id)
        if record is None:
            return None
        return self._root_dir / record.sku / record.filename

    def list_master_skus(self) -> set[str]:
        """登録済み SKU の集合を返す。"""
        with self._lock:
            return {record.sku for record in self._records_by_id.values()}

    def list_sku_phashes(
        self,
        *,
        allowed_skus: Optional[set[str]] = None,
    ) -> dict[str, list[str]]:
        """SKU ごとの pHash 一覧を返す。

        主要変数:
            allowed: フィルタ対象 SKU 集合。None の場合は全SKUを対象とする。
            output: `{"SKU": ["phash1", "phash2"]}` 形式の返却値。

        Note:
            - `phash` 欠損レコードは遅延計算を試行し、成功時は index.json を更新する。
            - 計算に失敗した画像はスキップし、例外で処理全体を止めない。
        """
        allowed = {normalize_sku(sku) for sku in allowed_skus} if allowed_skus else None
        output: dict[str, list[str]] = {}
        is_updated = False

        with self._lock:
            records = sorted(
                self._records_by_id.values(),
                key=lambda item: item.created_at,
            )
            for record in records:
                if allowed is not None and record.sku not in allowed:
                    continue

                phash = record.phash
                if not phash:
                    phash = self._compute_phash_from_stored_image(record)
                    if phash:
                        updated = ProductImageRecord(
                            image_id=record.image_id,
                            sku=record.sku,
                            filename=record.filename,
                            content_type=record.content_type,
                            created_at=record.created_at,
                            note=record.note,
                            phash=phash,
                        )
                        self._records_by_id[record.image_id] = updated
                        is_updated = True

                if not phash:
                    continue

                sku_hashes = output.setdefault(record.sku, [])
                sku_hashes.append(phash)

            if is_updated:
                self._save_index()
        return output

    def delete_image(self, image_id: str) -> bool:
        """image_id に対応する画像を削除する。

        Note:
            - ファイル削除に失敗した場合は RuntimeError を送出する。
        """
        with self._lock:
            record = self._records_by_id.get(image_id)
            if record is None:
                return False

            image_path = self._root_dir / record.sku / record.filename
            try:
                if image_path.exists():
                    image_path.unlink()
            except OSError as exc:
                raise RuntimeError(
                    f"画像ファイル削除に失敗しました: {image_path}"
                ) from exc

            self._records_by_id.pop(image_id, None)
            self._save_index()
            return True

    def _load_index(self) -> None:
        """index.json を読み込み、メモリに復元する。"""
        if not self._index_path.exists():
            self._save_index()
            return

        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        records: dict[str, ProductImageRecord] = {}
        for item in items:
            record = ProductImageRecord(
                image_id=str(item["image_id"]),
                sku=normalize_sku(str(item["sku"])),
                filename=str(item["filename"]),
                content_type=str(item["content_type"]),
                created_at=datetime.fromisoformat(str(item["created_at"])),
                note=(str(item["note"]) if item.get("note") else None),
                phash=(str(item["phash"]) if item.get("phash") else None),
            )
            records[record.image_id] = record
        self._records_by_id = records

    def _save_index(self) -> None:
        """メモリ上のレコードを index.json に保存する。"""
        records = sorted(self._records_by_id.values(), key=lambda item: item.created_at)
        payload = {
            "version": INDEX_VERSION,
            "items": [
                {
                    "image_id": record.image_id,
                    "sku": record.sku,
                    "filename": record.filename,
                    "content_type": record.content_type,
                    "created_at": record.created_at.isoformat(),
                    "note": record.note,
                    "phash": record.phash,
                }
                for record in records
            ],
        }
        self._index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _compute_phash_safe(self, *, image_bytes: bytes) -> Optional[str]:
        """画像バイト列から pHash を安全に計算する。"""
        try:
            return compute_phash_hex(image_bytes)
        except Exception:  # noqa: BLE001
            return None

    def _compute_phash_from_stored_image(
        self,
        record: ProductImageRecord,
    ) -> Optional[str]:
        """保存済み画像から pHash を計算する。"""
        image_path = self._root_dir / record.sku / record.filename
        if not image_path.exists():
            return None
        try:
            image_bytes = image_path.read_bytes()
        except OSError:
            return None
        return self._compute_phash_safe(image_bytes=image_bytes)


_PRODUCT_IMAGE_STORE: Optional[ProductImageStore] = None


def get_product_image_store() -> ProductImageStore:
    """商品画像マスターストアのシングルトンを返す。"""
    global _PRODUCT_IMAGE_STORE
    if _PRODUCT_IMAGE_STORE is None:
        _PRODUCT_IMAGE_STORE = ProductImageStore(
            root_dir=Path("storage/product_images")
        )
    return _PRODUCT_IMAGE_STORE
