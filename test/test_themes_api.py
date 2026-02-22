"""Theme API と theme連動infer のテスト。

検証対象:
- Theme CRUD（GET/POST/GET by id/PUT/DELETE）
- infer で theme_id を指定したときの候補制限
- 不正 theme_id に対する 404 応答
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


def _register_master_image(client: TestClient, sku: str) -> None:
    """推論候補に使う商品画像マスターを登録する。"""
    response = client.post(
        "/product-images",
        data={"sku": sku},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert response.status_code == 201


def test_theme_crud_flow(client: TestClient) -> None:
    """Theme CRUD の一連処理が成立することを確認する。"""
    create_response = client.post(
        "/themes",
        json={
            "name": "朝パン",
            "sku_list": ["BREAD-001", "BREAD-001", "CAKE-001"],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    theme_id = created["theme_id"]
    assert created["name"] == "朝パン"
    assert created["sku_list"] == ["BREAD-001", "CAKE-001"]

    list_response = client.get("/themes")
    assert list_response.status_code == 200
    listed_ids = [item["theme_id"] for item in list_response.json()]
    assert theme_id in listed_ids

    get_response = client.get(f"/themes/{theme_id}")
    assert get_response.status_code == 200
    got = get_response.json()
    assert got["theme_id"] == theme_id
    assert got["sku_list"] == ["BREAD-001", "CAKE-001"]

    update_response = client.put(
        f"/themes/{theme_id}",
        json={"name": "昼パン", "sku_list": ["TEST-SKU", "TEST-SKU", "BREAD-002"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "昼パン"
    assert updated["sku_list"] == ["TEST-SKU", "BREAD-002"]

    delete_response = client.delete(f"/themes/{theme_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True, "theme_id": theme_id}

    missing_response = client.get(f"/themes/{theme_id}")
    assert missing_response.status_code == 404
    assert "theme_id が存在しません" in missing_response.json()["detail"]


def test_infer_filters_candidates_by_theme(client: TestClient) -> None:
    """theme_id により infer 候補が theme.sku_list に制限されることを確認する。"""
    _register_master_image(client, "BREAD-001")
    _register_master_image(client, "CAKE-001")
    _register_master_image(client, "TEST-SKU")

    theme_response = client.post(
        "/themes",
        json={"name": "焼き菓子", "sku_list": ["BREAD-001", "CAKE-001"]},
    )
    assert theme_response.status_code == 201
    theme_id = theme_response.json()["theme_id"]

    scan_response = client.post(
        "/scans",
        data={"store_id": "store-01", "theme_id": theme_id},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert scan_response.status_code == 200
    scan_id = scan_response.json()["scan_id"]
    assert scan_response.json()["theme_id"] == theme_id

    infer_response = client.post(f"/scans/{scan_id}/infer", json={"top_k": 5})
    assert infer_response.status_code == 200

    payload = infer_response.json()
    candidates = payload["detections"][0]["candidates"]
    candidate_skus = [item["sku"] for item in candidates]
    assert candidate_skus == ["BREAD-001", "CAKE-001"]


def test_infer_returns_404_for_unknown_theme_id(client: TestClient) -> None:
    """存在しない theme_id を infer に指定した場合に 404 を返すことを確認する。"""
    scan_response = client.post(
        "/scans",
        data={"store_id": "store-01"},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert scan_response.status_code == 200
    scan_id = scan_response.json()["scan_id"]

    infer_response = client.post(
        f"/scans/{scan_id}/infer",
        json={"top_k": 3, "theme_id": "theme-not-found"},
    )
    assert infer_response.status_code == 404
    assert "theme_id が存在しません" in infer_response.json()["detail"]


def test_theme_validation_rejects_empty_name_and_sku(client: TestClient) -> None:
    """Theme バリデーションで空 name / 空 sku を拒否することを確認する。"""
    name_error = client.post("/themes", json={"name": "   ", "sku_list": ["TEST-SKU"]})
    assert name_error.status_code == 422

    sku_error = client.post("/themes", json={"name": "有効名", "sku_list": ["  "]})
    assert sku_error.status_code == 422
