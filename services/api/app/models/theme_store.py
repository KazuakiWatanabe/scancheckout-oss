"""Theme 情報の最小永続化ストア。

本モジュールは DB 導入前の MVP 用に、以下を担当する。
- Theme（候補 SKU 集合）の JSON 永続化
- Theme の CRUD（作成・取得・更新・削除）

Note:
    - JSON ファイルは `storage/themes/themes.json` に保存する。
    - routes 層は本モジュール経由で永続化を扱い、I/O の責務を分離する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class ThemeRecord:
    """1件の Theme を表すレコード。

    主要変数:
        theme_id: Theme 識別子（UUID文字列）。
        name: Theme の表示名。
        sku_list: 候補集合として許可する SKU 配列。
        created_at: 作成時刻（UTC）。
        updated_at: 更新時刻（UTC）。
    """

    theme_id: str
    name: str
    sku_list: list[str]
    created_at: datetime
    updated_at: datetime


class JsonThemeStore:
    """Theme を JSON ファイルへ保存するストア。"""

    def __init__(self, file_path: Path) -> None:
        """ストアを初期化する。

        Note:
            - file_path が存在しない場合は空データで開始する。
        """
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._records: dict[str, ThemeRecord] = {}
        self._load_from_disk()

    def list_themes(self) -> list[ThemeRecord]:
        """Theme 一覧を作成日時順で返す。"""
        with self._lock:
            return sorted(self._records.values(), key=lambda item: item.created_at)

    def get_theme(self, theme_id: str) -> Optional[ThemeRecord]:
        """theme_id に一致する Theme を返す。存在しない場合は None。"""
        with self._lock:
            return self._records.get(theme_id)

    def create_theme(self, *, name: str, sku_list: list[str]) -> ThemeRecord:
        """Theme を新規作成する。"""
        now = datetime.now(timezone.utc)
        record = ThemeRecord(
            theme_id=str(uuid4()),
            name=name,
            sku_list=sku_list,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[record.theme_id] = record
            self._save_to_disk()
            return record

    def update_theme(
        self,
        *,
        theme_id: str,
        name: str,
        sku_list: list[str],
    ) -> Optional[ThemeRecord]:
        """Theme を更新する。存在しない場合は None。"""
        with self._lock:
            current = self._records.get(theme_id)
            if current is None:
                return None

            updated = ThemeRecord(
                theme_id=current.theme_id,
                name=name,
                sku_list=sku_list,
                created_at=current.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._records[theme_id] = updated
            self._save_to_disk()
            return updated

    def delete_theme(self, theme_id: str) -> bool:
        """Theme を削除する。削除できた場合に True を返す。"""
        with self._lock:
            existed = theme_id in self._records
            if not existed:
                return False

            self._records.pop(theme_id, None)
            self._save_to_disk()
            return True

    def _load_from_disk(self) -> None:
        """JSON ファイルから Theme データを読み込む。"""
        if not self._file_path.exists():
            return

        raw = json.loads(self._file_path.read_text(encoding="utf-8"))
        records: dict[str, ThemeRecord] = {}
        for item in raw:
            record = ThemeRecord(
                theme_id=str(item["theme_id"]),
                name=str(item["name"]),
                sku_list=[str(sku) for sku in item.get("sku_list", [])],
                created_at=datetime.fromisoformat(str(item["created_at"])),
                updated_at=datetime.fromisoformat(str(item["updated_at"])),
            )
            records[record.theme_id] = record

        self._records = records

    def _save_to_disk(self) -> None:
        """保持中の Theme データを JSON ファイルへ保存する。"""
        records = sorted(self._records.values(), key=lambda item: item.created_at)
        payload = [
            {
                "theme_id": record.theme_id,
                "name": record.name,
                "sku_list": record.sku_list,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
            }
            for record in records
        ]
        self._file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


_THEME_STORE: Optional[JsonThemeStore] = None


def get_theme_store() -> JsonThemeStore:
    """Theme ストアのシングルトンを返す。"""
    global _THEME_STORE
    if _THEME_STORE is None:
        _THEME_STORE = JsonThemeStore(file_path=Path("storage/themes/themes.json"))
    return _THEME_STORE
