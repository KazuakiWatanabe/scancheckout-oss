"""POST /pos/checkout ルートの結合テスト。

テスト方針
- FastAPI TestClient を使い、実際の HTTP リクエスト/レスポンスを検証する。
- build_odoo_adapter_from_env をモックして実 Odoo 不要にする。
- 対象ケース:
  - API 成功ケース（mode="sale", sale.order 作成・確定）
  - mode="pos" → HTTP 400
  - OdooJsonRpcError → HTTP 502
  - その他の例外 → HTTP 500
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.pos_adapters.odoo_jsonrpc import OdooJsonRpcError
from app.routes.pos import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ============================================================
# テスト用 FastAPI アプリとクライアント
# ============================================================


@pytest.fixture()
def client() -> TestClient:
    """ルートを組み込んだ最小 FastAPI アプリの TestClient を返す。"""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _sale_body(**overrides: object) -> dict:
    """mode="sale" の最小リクエストボディを返す補助関数。"""
    body: dict = {
        "store_id": "store-1",
        "mode": "sale",
        "lines": [{"sku": "SKU-A", "qty": 1.0}],
    }
    body.update(overrides)
    return body


def _mock_adapter(so_id: int = 10, confirm_result: object = True) -> MagicMock:
    """create_sale_order_draft / confirm_sale_order を設定済みのモックアダプタを返す。"""
    adapter = MagicMock()
    # cfg.default_partner_id / default_pricelist_id を参照するため設定しておく。
    adapter.cfg.default_partner_id = 1
    adapter.cfg.default_pricelist_id = None
    adapter.create_sale_order_draft.return_value = so_id
    adapter.confirm_sale_order.return_value = confirm_result
    return adapter


# ============================================================
# 正常系テスト
# ============================================================


class TestCheckoutSaleSuccess:
    """mode="sale" 正常系のテスト。"""

    def test_returns_200_with_ok(self, client: TestClient) -> None:
        """正常時は HTTP 200、ok=True、target="sale.order" を返す。"""
        adapter = _mock_adapter(so_id=42)
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["target"] == "sale.order"
        assert data["record_id"] == 42
        assert data["message"] is None

    def test_record_id_is_int(self, client: TestClient) -> None:
        """record_id が整数で返ることを確認する。"""
        adapter = _mock_adapter(so_id=99)
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert resp.status_code == 200
        assert isinstance(resp.json()["record_id"], int)

    def test_raw_field_absent(self, client: TestClient) -> None:
        """レスポンスに raw フィールドが含まれないことを確認する。"""
        adapter = _mock_adapter()
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert "raw" not in resp.json()

    def test_note_passed_to_adapter(self, client: TestClient) -> None:
        """note が create_sale_order_draft に渡されることを確認する。"""
        adapter = _mock_adapter()
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            client.post("/pos/checkout", json=_sale_body(note="テストメモ"))

        _, kwargs = adapter.create_sale_order_draft.call_args
        assert kwargs.get("note") == "テストメモ"

    def test_confirm_called_with_so_id(self, client: TestClient) -> None:
        """confirm_sale_order が create の戻り値（so_id）で呼ばれることを確認する。"""
        adapter = _mock_adapter(so_id=55)
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            client.post("/pos/checkout", json=_sale_body())

        adapter.confirm_sale_order.assert_called_once_with(55)


# ============================================================
# エラー系テスト
# ============================================================


class TestCheckoutModePos:
    """mode="pos" のテスト。"""

    def test_pos_mode_returns_400(self, client: TestClient) -> None:
        """mode="pos" は HTTP 400 を返す。"""
        resp = client.post("/pos/checkout", json=_sale_body(mode="pos"))
        assert resp.status_code == 400

    def test_pos_mode_detail_message(self, client: TestClient) -> None:
        """400 レスポンスに未対応の旨が含まれる。"""
        resp = client.post("/pos/checkout", json=_sale_body(mode="pos"))
        assert "未対応" in resp.json().get("detail", "")

    def test_pos_mode_adapter_not_called(self, client: TestClient) -> None:
        """mode="pos" のとき adapter は一切呼ばれない。"""
        adapter = _mock_adapter()
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            client.post("/pos/checkout", json=_sale_body(mode="pos"))

        adapter.create_sale_order_draft.assert_not_called()


class TestCheckoutOdooError:
    """OdooJsonRpcError → HTTP 502 のテスト。"""

    def test_create_draft_error_returns_502(self, client: TestClient) -> None:
        """create_sale_order_draft が OdooJsonRpcError を送出すると HTTP 502 を返す。"""
        adapter = _mock_adapter()
        adapter.create_sale_order_draft.side_effect = OdooJsonRpcError("Odoo down")
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert resp.status_code == 502

    def test_confirm_error_returns_502(self, client: TestClient) -> None:
        """confirm_sale_order が OdooJsonRpcError を送出すると HTTP 502 を返す。"""
        adapter = _mock_adapter()
        adapter.confirm_sale_order.side_effect = OdooJsonRpcError("confirm failed")
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert resp.status_code == 502

    def test_502_detail_contains_odoo_error(self, client: TestClient) -> None:
        """502 レスポンスの detail に Odoo エラー文字列が含まれる。"""
        adapter = _mock_adapter()
        adapter.create_sale_order_draft.side_effect = OdooJsonRpcError("SKU not found")
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert "Odoo エラー" in resp.json().get("detail", "")


class TestCheckoutUnexpectedError:
    """予期しない例外 → HTTP 500 のテスト。"""

    def test_unexpected_error_returns_500(self, client: TestClient) -> None:
        """adapter が予期しない例外を送出すると HTTP 500 を返す。"""
        adapter = _mock_adapter()
        adapter.create_sale_order_draft.side_effect = RuntimeError("unexpected")
        with patch("app.routes.pos.build_odoo_adapter_from_env", return_value=adapter):
            resp = client.post("/pos/checkout", json=_sale_body())

        assert resp.status_code == 500


class TestCheckoutValidation:
    """リクエストバリデーションのテスト。"""

    def test_missing_lines_returns_422(self, client: TestClient) -> None:
        """lines が空の場合は 422 を返す。"""
        body = {"store_id": "store-1", "mode": "sale"}
        resp = client.post("/pos/checkout", json=body)
        assert resp.status_code == 422

    def test_invalid_qty_returns_422(self, client: TestClient) -> None:
        """qty が 0 以下の場合は 422 を返す。"""
        resp = client.post(
            "/pos/checkout",
            json=_sale_body(lines=[{"sku": "SKU-A", "qty": 0}]),
        )
        assert resp.status_code == 422
