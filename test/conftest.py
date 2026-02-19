"""API テスト共通フィクスチャ。

本ファイルは `/test` 配下の pytest 実行に必要な共通準備を行う。
- `services/api` を import path に追加
- TestClient の生成
- スキャンストアをテスト専用ディレクトリへ差し替え

Note:
    - `app.models.scan_store._SCAN_STORE` はグローバル状態のため、
      各テストで初期化し直す。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# リポジトリルートと API ルートを解決する。
REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "api"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402
from app.models import scan_store as scan_store_module  # noqa: E402


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """テスト用 TestClient を返す。

    主要変数:
        tmp_path: pytest が提供する一時ディレクトリ。
        image_dir: アップロード画像の保存先。
    """
    image_dir = tmp_path / "images"
    scan_store_module._SCAN_STORE = scan_store_module.InMemoryScanStore(image_dir=image_dir)

    with TestClient(app) as test_client:
        yield test_client

    scan_store_module._SCAN_STORE = None
