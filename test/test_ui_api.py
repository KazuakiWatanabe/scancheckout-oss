"""UI 静的配信の API テスト。

検証対象:
- GET / （/ui へのリダイレクト）
- GET /ui/ （index.html の配信）
- GET /ui/app.js （UI スクリプト配信）

Note:
    - UI の見た目ではなく、配信経路と最低限のコンテンツ存在を検証する。
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_redirects_to_ui(client: TestClient) -> None:
    """`GET /` が `/ui/` へリダイレクトすることを確認する。"""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_ui_index_is_served(client: TestClient) -> None:
    """`GET /ui/` で UI の HTML が取得できることを確認する。"""
    response = client.get("/ui/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "撮影 → 候補提示 → 確定 → Odoo登録" in response.text
    assert 'id="cameraPreview"' in response.text


def test_ui_script_is_served(client: TestClient) -> None:
    """`GET /ui/app.js` で UI スクリプトが取得できることを確認する。"""
    response = client.get("/ui/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert "captureAndUploadScan" in response.text
