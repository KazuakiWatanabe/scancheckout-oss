"""商品画像マスター API のテスト。

検証対象:
- POST /product-images
- GET /product-images
- GET /product-images/{image_id}/file
- DELETE /product-images/{image_id}
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


def test_product_images_upload_list_and_get_file(client: TestClient) -> None:
    """画像登録後に一覧取得と画像本体取得ができることを確認する。"""
    create_response = client.post(
        "/product-images",
        data={"sku": "SKU-001", "note": "正面"},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["ok"] is True
    assert created["sku"] == "SKU-001"

    image_id = created["image_id"]
    list_response = client.get("/product-images", params={"sku": "SKU-001"})
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["image_id"] == image_id
    assert listed[0]["sku"] == "SKU-001"
    assert listed[0]["note"] == "正面"

    file_response = client.get(f"/product-images/{image_id}/file")
    assert file_response.status_code == 200
    assert file_response.content == _sample_png_bytes()
    assert "image/png" in file_response.headers.get("content-type", "")


def test_product_images_rejects_unsupported_content_type(client: TestClient) -> None:
    """未対応 Content-Type のアップロードを 400 で拒否することを確認する。"""
    response = client.post(
        "/product-images",
        data={"sku": "SKU-001"},
        files={"image": ("sample.gif", b"gif89a", "image/gif")},
    )

    assert response.status_code == 400
    assert "未対応の Content-Type" in response.json()["detail"]


def test_product_images_rejects_oversize_file(client: TestClient) -> None:
    """5MB超過ファイルのアップロードを 413 で拒否することを確認する。"""
    oversize = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/product-images",
        data={"sku": "SKU-001"},
        files={"image": ("large.jpg", oversize, "image/jpeg")},
    )

    assert response.status_code == 413
    assert "ファイルサイズ上限超過" in response.json()["detail"]


def test_product_images_returns_404_for_unknown_resource(client: TestClient) -> None:
    """未存在 SKU / image_id に対して 404 を返すことを確認する。"""
    list_response = client.get("/product-images", params={"sku": "UNKNOWN-SKU"})
    assert list_response.status_code == 404
    assert "sku が存在しません" in list_response.json()["detail"]

    file_response = client.get("/product-images/not-found/file")
    assert file_response.status_code == 404
    assert "image_id が存在しません" in file_response.json()["detail"]


def test_product_images_delete_success(client: TestClient) -> None:
    """画像削除 API がメタデータとファイルを削除することを確認する。"""
    create_response = client.post(
        "/product-images",
        data={"sku": "SKU-DEL"},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert create_response.status_code == 201
    image_id = create_response.json()["image_id"]

    delete_response = client.delete(f"/product-images/{image_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True, "image_id": image_id}

    second_delete = client.delete(f"/product-images/{image_id}")
    assert second_delete.status_code == 404
