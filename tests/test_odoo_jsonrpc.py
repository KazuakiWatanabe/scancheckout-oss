"""odoo_jsonrpc アダプタの単体テスト。

テスト方針
- httpx.Client を unittest.mock.patch で差し替え、実 Odoo なしで検証する。
- 各テストは OdooJsonRpcError の送出・戻り値型・引数の正確さを確認する。

対象クラス
- OdooJsonRpcClient: authenticate / call_kw の通信エラー・Odoo エラー処理
- OdooPosAdapter:
  - resolve_product_ids_by_sku: 空リスト・SKU未存在・通信エラー
  - create_sale_order_draft: 戻り値型保証・SKU未存在
  - confirm_sale_order: 成功・Odoo エラー
  - checkout: 成功・失敗
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from services.api.app.pos_adapters.odoo_jsonrpc import (
    CheckoutLine,
    CheckoutRequest,
    OdooConfig,
    OdooJsonRpcClient,
    OdooJsonRpcError,
    OdooPosAdapter,
)

# ============================================================
# テスト用フィクスチャ
# ============================================================


def _make_cfg(**kwargs: Any) -> OdooConfig:
    """テスト用の最小 OdooConfig を生成する補助関数。"""
    defaults: dict[str, Any] = {
        "base_url": "http://odoo-test:8069",
        "db": "testdb",
        "username": "admin",
        "password": "admin",
    }
    defaults.update(kwargs)
    return OdooConfig(**defaults)


def _json_response(data: Any, status_code: int = 200) -> MagicMock:
    """httpx.Response を模倣したモックを返す補助関数。"""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    # raise_for_status は成功時に何もしない。
    resp.raise_for_status = MagicMock()
    return resp


def _error_json_response(status_code: int = 500) -> MagicMock:
    """HTTPStatusError を raise する httpx.Response モックを返す補助関数。"""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=resp,
    )
    return resp


# ============================================================
# OdooJsonRpcClient テスト
# ============================================================


class TestOdooJsonRpcClientAuthenticate:
    """OdooJsonRpcClient.authenticate のテスト。"""

    def test_authenticate_success(self) -> None:
        """正常認証時に uid（int）が返る。"""
        cfg = _make_cfg()
        client = OdooJsonRpcClient(cfg)

        auth_resp = _json_response({"result": {"uid": 1, "session_id": "abc"}})

        with patch.object(client._client, "post", return_value=auth_resp) as mock_post:
            uid = client.authenticate()

        assert uid == 1
        assert client._uid == 1
        mock_post.assert_called_once_with(
            "/web/session/authenticate", json=mock_post.call_args[1]["json"]
        )

    def test_authenticate_odoo_error(self) -> None:
        """Odoo が error フィールドを返した場合は OdooJsonRpcError を送出する。"""
        cfg = _make_cfg()
        client = OdooJsonRpcClient(cfg)
        err_resp = _json_response({"error": {"message": "invalid credentials"}})

        with patch.object(client._client, "post", return_value=err_resp):
            with pytest.raises(OdooJsonRpcError, match="authenticate error"):
                client.authenticate()

    def test_authenticate_http_error(self) -> None:
        """HTTP 5xx 時は OdooJsonRpcError（認証 HTTP エラー）を送出する。"""
        cfg = _make_cfg()
        client = OdooJsonRpcClient(cfg)
        bad_resp = _error_json_response(status_code=500)

        with patch.object(client._client, "post", return_value=bad_resp):
            with pytest.raises(OdooJsonRpcError, match="認証 HTTP エラー"):
                client.authenticate()

    def test_authenticate_request_error(self) -> None:
        """接続失敗時は OdooJsonRpcError（認証 通信エラー）を送出する。"""
        cfg = _make_cfg()
        client = OdooJsonRpcClient(cfg)

        with patch.object(
            client._client,
            "post",
            side_effect=httpx.ConnectError("connection refused"),
        ):
            with pytest.raises(OdooJsonRpcError, match="認証 通信エラー"):
                client.authenticate()

    def test_authenticate_missing_uid(self) -> None:
        """uid が result に含まれない場合は OdooJsonRpcError を送出する。"""
        cfg = _make_cfg()
        client = OdooJsonRpcClient(cfg)
        resp = _json_response({"result": {}})

        with patch.object(client._client, "post", return_value=resp):
            with pytest.raises(OdooJsonRpcError, match="uid が取得できませんでした"):
                client.authenticate()


class TestOdooJsonRpcClientCallKw:
    """OdooJsonRpcClient.call_kw のテスト。"""

    def _make_authenticated_client(self) -> OdooJsonRpcClient:
        """_uid 設定済みの OdooJsonRpcClient を返す補助メソッド。"""
        client = OdooJsonRpcClient(_make_cfg())
        # 認証済み状態をシミュレートする。
        client._uid = 1
        return client

    def test_call_kw_success(self) -> None:
        """正常時は result をそのまま返す。"""
        client = self._make_authenticated_client()
        resp = _json_response({"result": 42})

        with patch.object(client._client, "post", return_value=resp):
            result = client.call_kw("sale.order", "create", args=[{"partner_id": 1}])

        assert result == 42

    def test_call_kw_odoo_error(self) -> None:
        """Odoo が error フィールドを返した場合は OdooJsonRpcError を送出する。"""
        client = self._make_authenticated_client()
        resp = _json_response({"error": {"message": "Access Denied"}})

        with patch.object(client._client, "post", return_value=resp):
            with pytest.raises(OdooJsonRpcError, match="call_kw error"):
                client.call_kw("sale.order", "create", args=[{}])

    def test_call_kw_http_error(self) -> None:
        """HTTP 502 時は OdooJsonRpcError（call_kw HTTP エラー）を送出する。"""
        client = self._make_authenticated_client()
        bad_resp = _error_json_response(status_code=502)

        with patch.object(client._client, "post", return_value=bad_resp):
            with pytest.raises(OdooJsonRpcError, match="call_kw HTTP エラー"):
                client.call_kw("sale.order", "create", args=[{}])

    def test_call_kw_request_error(self) -> None:
        """タイムアウト時は OdooJsonRpcError（call_kw 通信エラー）を送出する。"""
        client = self._make_authenticated_client()

        with patch.object(
            client._client,
            "post",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            with pytest.raises(OdooJsonRpcError, match="call_kw 通信エラー"):
                client.call_kw("sale.order", "create", args=[{}])


# ============================================================
# OdooPosAdapter テスト
# ============================================================


def _make_adapter(**kwargs: Any) -> OdooPosAdapter:
    """テスト用 OdooPosAdapter を生成する補助関数。"""
    return OdooPosAdapter(_make_cfg(**kwargs))


class TestResolveProductIdsBySku:
    """OdooPosAdapter.resolve_product_ids_by_sku のテスト。"""

    def test_empty_skus_returns_empty_dict(self) -> None:
        """空リストを渡した場合は Odoo を呼ばず空辞書を返す。"""
        adapter = _make_adapter()
        # call_kw が呼ばれないことを確認するためにモックを設定しておく。
        adapter.client._uid = 1
        with patch.object(adapter.client, "call_kw") as mock_kw:
            result = adapter.resolve_product_ids_by_sku([])
        assert result == {}
        mock_kw.assert_not_called()

    def test_resolve_success(self) -> None:
        """SKU が見つかった場合は {sku: product_id} を返す。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        rows = [
            {"id": 10, "default_code": "SKU-A", "name": "Product A"},
            {"id": 20, "default_code": "SKU-B", "name": "Product B"},
        ]
        with patch.object(adapter.client, "call_kw", return_value=rows):
            result = adapter.resolve_product_ids_by_sku(["SKU-A", "SKU-B"])

        assert result == {"SKU-A": 10, "SKU-B": 20}

    def test_resolve_partial_miss(self) -> None:
        """Odoo が一部の SKU しか返さない場合、見つかった分だけ返す。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        rows = [{"id": 10, "default_code": "SKU-A", "name": "Product A"}]
        with patch.object(adapter.client, "call_kw", return_value=rows):
            result = adapter.resolve_product_ids_by_sku(["SKU-A", "SKU-MISSING"])

        assert result == {"SKU-A": 10}
        assert "SKU-MISSING" not in result

    def test_resolve_odoo_error_propagates(self) -> None:
        """Odoo 通信エラーは OdooJsonRpcError として上位へ伝播する。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        with patch.object(
            adapter.client, "call_kw", side_effect=OdooJsonRpcError("Odoo down")
        ):
            with pytest.raises(OdooJsonRpcError, match="Odoo down"):
                adapter.resolve_product_ids_by_sku(["SKU-X"])


class TestCreateSaleOrderDraft:
    """OdooPosAdapter.create_sale_order_draft のテスト。"""

    def _lines(self) -> list[CheckoutLine]:
        """テスト用明細を返す補助メソッド。"""
        return [CheckoutLine(sku="SKU-A", qty=2.0)]

    def test_create_success_returns_int(self) -> None:
        """正常時は sale.order ID（int）を返す。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        sku_map = {"SKU-A": 10}
        with patch.object(adapter, "resolve_product_ids_by_sku", return_value=sku_map):
            with patch.object(adapter.client, "call_kw", return_value=99):
                so_id = adapter.create_sale_order_draft(
                    partner_id=1, lines=self._lines()
                )

        assert so_id == 99
        assert isinstance(so_id, int)

    def test_unknown_sku_raises(self) -> None:
        """存在しない SKU を含む場合は OdooJsonRpcError を送出する。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        # SKU-A は解決できず空辞書が返る。
        with patch.object(adapter, "resolve_product_ids_by_sku", return_value={}):
            with pytest.raises(OdooJsonRpcError, match="Unknown SKU"):
                adapter.create_sale_order_draft(partner_id=1, lines=self._lines())

    def test_create_returns_none_raises(self) -> None:
        """Odoo が None を返した場合は OdooJsonRpcError（不正な戻り値）を送出する。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        sku_map = {"SKU-A": 10}
        with patch.object(adapter, "resolve_product_ids_by_sku", return_value=sku_map):
            with patch.object(adapter.client, "call_kw", return_value=None):
                with pytest.raises(OdooJsonRpcError, match="不正な戻り値"):
                    adapter.create_sale_order_draft(partner_id=1, lines=self._lines())

    def test_create_returns_invalid_type_raises(self) -> None:
        """Odoo が文字列などを返した場合は OdooJsonRpcError（不正な戻り値）を送出する。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        sku_map = {"SKU-A": 10}
        with patch.object(adapter, "resolve_product_ids_by_sku", return_value=sku_map):
            with patch.object(adapter.client, "call_kw", return_value="not-an-int"):
                with pytest.raises(OdooJsonRpcError, match="不正な戻り値"):
                    adapter.create_sale_order_draft(partner_id=1, lines=self._lines())


class TestConfirmSaleOrder:
    """OdooPosAdapter.confirm_sale_order のテスト。"""

    def test_confirm_success(self) -> None:
        """正常時は call_kw の戻り値（True など）をそのまま返す。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        with patch.object(adapter.client, "call_kw", return_value=True):
            result = adapter.confirm_sale_order(sale_order_id=99)

        assert result is True

    def test_confirm_odoo_error_propagates(self) -> None:
        """Odoo エラー時は OdooJsonRpcError をそのまま伝播する。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        with patch.object(
            adapter.client,
            "call_kw",
            side_effect=OdooJsonRpcError("action_confirm failed"),
        ):
            with pytest.raises(OdooJsonRpcError, match="action_confirm failed"):
                adapter.confirm_sale_order(sale_order_id=99)

    def test_confirm_unexpected_error_wrapped(self) -> None:
        """予期しない例外は OdooJsonRpcError にラップされる。"""
        adapter = _make_adapter()
        adapter.client._uid = 1

        with patch.object(
            adapter.client,
            "call_kw",
            side_effect=ValueError("unexpected"),
        ):
            with pytest.raises(OdooJsonRpcError, match="action_confirm に失敗しました"):
                adapter.confirm_sale_order(sale_order_id=99)


class TestCheckout:
    """OdooPosAdapter.checkout のテスト（sale.order フロー）。"""

    def _req(self) -> CheckoutRequest:
        """テスト用 CheckoutRequest を返す補助メソッド。"""
        return CheckoutRequest(
            store_id="store-1",
            operator_id="op-1",
            lines=[CheckoutLine(sku="SKU-A", qty=1.0)],
        )

    def test_checkout_success(self) -> None:
        """正常時は ok=True, target="sale.order", record_id=int を返す。"""
        adapter = _make_adapter()

        with patch.object(
            adapter, "create_sale_order_draft", return_value=10
        ) as mock_create:
            with patch.object(
                adapter, "confirm_sale_order", return_value=True
            ) as mock_confirm:
                result = adapter.checkout(self._req())

        assert result.ok is True
        assert result.target == "sale.order"
        assert result.record_id == 10
        assert result.message is None
        mock_create.assert_called_once()
        mock_confirm.assert_called_once_with(10)

    def test_checkout_create_failure(self) -> None:
        """create_sale_order_draft 失敗時は ok=False を返す。"""
        adapter = _make_adapter()

        with patch.object(
            adapter,
            "create_sale_order_draft",
            side_effect=OdooJsonRpcError("create failed"),
        ):
            result = adapter.checkout(self._req())

        assert result.ok is False
        assert result.target == "sale.order"
        assert result.record_id is None
        assert "create failed" in (result.message or "")

    def test_checkout_confirm_failure(self) -> None:
        """confirm_sale_order 失敗時は ok=False を返す。"""
        adapter = _make_adapter()

        with patch.object(adapter, "create_sale_order_draft", return_value=10):
            with patch.object(
                adapter,
                "confirm_sale_order",
                side_effect=OdooJsonRpcError("confirm failed"),
            ):
                result = adapter.checkout(self._req())

        assert result.ok is False
        assert "confirm failed" in (result.message or "")
