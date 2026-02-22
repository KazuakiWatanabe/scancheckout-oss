"""infer の master_skus 連動テスト。

検証対象:
- master_skus が候補母集団として使われること
- master_skus が空の場合に候補が空になること
- Theme 指定時に積集合で絞り込まれること
- top_k 制限が適用されること
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


def _create_scan(client: TestClient) -> str:
    """テスト用 scan を1件作成して scan_id を返す。"""
    response = client.post(
        "/scans",
        data={"store_id": "store-01"},
        files={"image": ("sample.png", _sample_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    return response.json()["scan_id"]


def _infer_candidate_skus(
    client: TestClient,
    *,
    scan_id: str,
    top_k: int,
    theme_id: str | None = None,
) -> list[str]:
    """infer 実行結果から candidate SKU 一覧を返す。"""
    response = client.post(
        f"/scans/{scan_id}/infer",
        json={"top_k": top_k, "theme_id": theme_id},
    )
    assert response.status_code == 200
    payload = response.json()
    return [item["sku"] for item in payload["detections"][0]["candidates"]]


def test_infer_uses_master_skus_as_catalog(client: TestClient) -> None:
    """master_skus が候補母集団として使われることを確認する。"""
    _register_master_image(client, "BREAD-002")
    _register_master_image(client, "CAKE-001")
    _register_master_image(client, "BREAD-001")

    scan_id = _create_scan(client)
    candidate_skus = _infer_candidate_skus(client, scan_id=scan_id, top_k=5)

    assert candidate_skus == ["BREAD-001", "BREAD-002", "CAKE-001"]


def test_infer_returns_empty_when_master_skus_is_empty(client: TestClient) -> None:
    """master_skus が空なら候補が空になることを確認する。"""
    scan_id = _create_scan(client)
    candidate_skus = _infer_candidate_skus(client, scan_id=scan_id, top_k=3)

    assert candidate_skus == []


def test_infer_intersects_theme_and_master_skus(client: TestClient) -> None:
    """Theme 指定時に theme_skus と master_skus の積集合のみ返すことを確認する。"""
    _register_master_image(client, "BREAD-001")
    _register_master_image(client, "TEST-SKU")

    theme_response = client.post(
        "/themes",
        json={"name": "target", "sku_list": ["BREAD-001", "BREAD-002", "OUTSIDE-001"]},
    )
    assert theme_response.status_code == 201
    theme_id = theme_response.json()["theme_id"]

    scan_id = _create_scan(client)
    candidate_skus = _infer_candidate_skus(
        client,
        scan_id=scan_id,
        top_k=5,
        theme_id=theme_id,
    )

    assert candidate_skus == ["BREAD-001"]


def test_infer_respects_top_k_with_master_skus(client: TestClient) -> None:
    """top_k で返却件数が制限されることを確認する。"""
    _register_master_image(client, "BREAD-001")
    _register_master_image(client, "BREAD-002")
    _register_master_image(client, "CAKE-001")

    scan_id = _create_scan(client)
    candidate_skus = _infer_candidate_skus(client, scan_id=scan_id, top_k=2)

    assert candidate_skus == ["BREAD-001", "BREAD-002"]
