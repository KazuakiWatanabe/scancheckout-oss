"""API テスト共通フィクスチャ。

本ファイルは `/test` 配下の pytest 実行に必要な共通準備を行う。
- `services/api` を import path に追加
- TestClient の生成
- スキャンストアをテスト専用ディレクトリへ差し替え

Note:
    - `app.models.scan_store._SCAN_STORE` はグローバル状態のため、
      各テストで初期化し直す。
    - `app.models.theme_store._THEME_STORE` も同様に初期化する。
    - `app.models.product_image_store._PRODUCT_IMAGE_STORE` も同様に初期化する。
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
from app.models import product_image_store as product_image_store_module  # noqa: E402
from app.models import scan_store as scan_store_module  # noqa: E402
from app.models import theme_store as theme_store_module  # noqa: E402


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """テスト用 TestClient を返す。

    主要変数:
        tmp_path: pytest が提供する一時ディレクトリ。
        image_dir: アップロード画像の保存先。
        theme_file: Theme JSON 保存先。
        product_image_root: 商品画像マスターの保存先。
    """
    image_dir = tmp_path / "images"
    theme_file = tmp_path / "themes" / "themes.json"
    product_image_root = tmp_path / "product_images"
    scan_store_module._SCAN_STORE = scan_store_module.InMemoryScanStore(
        image_dir=image_dir
    )
    theme_store_module._THEME_STORE = theme_store_module.JsonThemeStore(
        file_path=theme_file
    )
    product_image_store_module._PRODUCT_IMAGE_STORE = (
        product_image_store_module.ProductImageStore(root_dir=product_image_root)
    )

    with TestClient(app) as test_client:
        yield test_client

    scan_store_module._SCAN_STORE = None
    theme_store_module._THEME_STORE = None
    product_image_store_module._PRODUCT_IMAGE_STORE = None
