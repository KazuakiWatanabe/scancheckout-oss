"""スキャン情報の最小永続化ストア。

本モジュールは DB 導入前の MVP 用に、以下を担当する。
- アップロード画像のローカル保存
- scan_id 単位のメタ情報管理
- 推論結果（detections）の保持

Note:
    - 本実装はプロセス内メモリを利用するため、API 再起動でメタ情報は失われる。
    - 画像ファイルは SCAN_IMAGE_DIR（既定: storage/images）に保存する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import uuid4


@dataclass
class ScanRecord:
    """1件のスキャンを表すレコード。

    主要変数:
        scan_id: スキャン識別子（UUID 文字列）。
        store_id: 店舗識別子。
        device_id: 端末識別子（任意）。
        image_uri: 保存画像のローカル URI。
        content_type: アップロード時の MIME タイプ。
        size_bytes: 画像サイズ（バイト）。
        created_at: 作成時刻（UTC）。
        detections: 推論結果（bbox + 候補）配列。
        model_version: 推論ロジックのバージョン識別子。
    """

    scan_id: str
    store_id: str
    device_id: Optional[str]
    image_uri: str
    content_type: str
    size_bytes: int
    created_at: datetime
    detections: list[dict[str, Any]] = field(default_factory=list)
    model_version: Optional[str] = None


class InMemoryScanStore:
    """スキャン情報を管理するインメモリストア。"""

    def __init__(self, image_dir: Path) -> None:
        """ストアを初期化する。

        Note:
            - image_dir は存在しない場合に作成する。
        """
        self._image_dir = image_dir
        self._image_dir.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, ScanRecord] = {}
        self._lock = Lock()

    def create_scan(
        self,
        *,
        store_id: str,
        device_id: Optional[str],
        filename: str,
        content_type: str,
        image_bytes: bytes,
    ) -> ScanRecord:
        """画像を保存し、ScanRecord を生成して保持する。"""
        suffix = Path(filename or "").suffix
        safe_suffix = suffix if 0 < len(suffix) <= 10 else ".bin"
        scan_id = str(uuid4())
        image_path = self._image_dir / f"{scan_id}{safe_suffix}"

        image_path.write_bytes(image_bytes)
        record = ScanRecord(
            scan_id=scan_id,
            store_id=store_id,
            device_id=device_id,
            image_uri=str(image_path.resolve()),
            content_type=content_type,
            size_bytes=len(image_bytes),
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._records[scan_id] = record
        return record

    def get_scan(self, scan_id: str) -> Optional[ScanRecord]:
        """scan_id に対応するレコードを返す。存在しない場合は None。"""
        with self._lock:
            return self._records.get(scan_id)

    def load_image_bytes(self, scan_id: str) -> bytes:
        """保存済み画像のバイト列を返す。"""
        record = self.get_scan(scan_id)
        if record is None:
            raise KeyError(scan_id)
        return Path(record.image_uri).read_bytes()

    def save_detections(
        self,
        *,
        scan_id: str,
        detections: list[dict[str, Any]],
        model_version: str,
    ) -> ScanRecord:
        """推論結果をレコードに保存する。"""
        with self._lock:
            record = self._records.get(scan_id)
            if record is None:
                raise KeyError(scan_id)
            record.detections = detections
            record.model_version = model_version
            self._records[scan_id] = record
            return record


_SCAN_STORE: Optional[InMemoryScanStore] = None


def get_scan_store() -> InMemoryScanStore:
    """スキャンストアのシングルトンを返す。"""
    global _SCAN_STORE
    if _SCAN_STORE is None:
        _SCAN_STORE = InMemoryScanStore(image_dir=Path("storage/images"))
    return _SCAN_STORE
