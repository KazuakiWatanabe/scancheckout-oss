"""スキャン API のエンドツーエンドテスト。

検証対象
- GET /health
- POST /scans
- POST /scans/{scan_id}/infer

Note:
    - 認識はダミー推論のため、候補 SKU の固定値を厳密には固定しない。
    - 代わりに件数・形式・スコア範囲を検証する。
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _sample_png_bytes() -> bytes:
    """1x1 PNG 画像のバイト列を返す。"""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc\xff"
        b"\x1f\x00\x03\x03\x02\x00\xee\x98\xc4\x9d\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_health_returns_ok(client: TestClient) -> None:
    """`GET /health` が稼働状態を返すことを確認する。"""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_scan_and_infer_success(client: TestClient) -> None:
    """画像アップロードから推論まで一連処理が成功することを確認する。"""
    upload_response = client.post(
        "/scans",
        data={"store_id": "store-01", "device_id": "device-01"},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 200

    scan_payload = upload_response.json()
    scan_id = scan_payload["scan_id"]
    assert scan_payload["store_id"] == "store-01"
    assert scan_payload["device_id"] == "device-01"
    assert scan_payload["content_type"] == "image/png"
    assert scan_payload["size_bytes"] > 0

    infer_response = client.post(
        f"/scans/{scan_id}/infer",
        json={"top_k": 3, "theme_id": "theme-bakery"},
    )
    assert infer_response.status_code == 200

    infer_payload = infer_response.json()
    assert infer_payload["scan_id"] == scan_id
    assert infer_payload["model_version"] == "dummy-hash-v1"
    assert len(infer_payload["detections"]) == 1
    assert infer_payload["detections"][0]["bbox"] == [0.0, 0.0, 1.0, 1.0]
    assert len(infer_payload["detections"][0]["candidates"]) == 3

    for candidate in infer_payload["detections"][0]["candidates"]:
        assert isinstance(candidate["sku"], str)
        assert isinstance(candidate["name"], str)
        assert 0.0 <= candidate["score"] <= 1.0


def test_create_scan_rejects_non_image(client: TestClient) -> None:
    """`POST /scans` が非画像ファイルを拒否することを確認する。"""
    response = client.post(
        "/scans",
        data={"store_id": "store-01"},
        files={"image": ("sample.txt", b"plain-text", "text/plain")},
    )

    assert response.status_code == 400
    assert "画像ファイルのみ受け付けます" in response.json()["detail"]


def test_infer_accepts_null_theme_id(client: TestClient) -> None:
    """`theme_id` が null でも infer が成功することを確認する。"""
    upload_response = client.post(
        "/scans",
        data={"store_id": "store-02"},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 200
    scan_id = upload_response.json()["scan_id"]

    infer_response = client.post(
        f"/scans/{scan_id}/infer",
        json={"top_k": 2, "theme_id": None},
    )
    assert infer_response.status_code == 200
    payload = infer_response.json()
    assert payload["scan_id"] == scan_id
    assert len(payload["detections"][0]["candidates"]) == 2


def test_infer_returns_404_for_unknown_scan(client: TestClient) -> None:
    """存在しない scan_id への推論要求が 404 を返すことを確認する。"""
    response = client.post("/scans/not-found-scan/infer", json={"top_k": 2})

    assert response.status_code == 404
    assert "scan_id が存在しません" in response.json()["detail"]
