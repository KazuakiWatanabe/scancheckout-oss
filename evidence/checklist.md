# DoD チェックリスト（PR 添付用）

- [x] 日本語 docstring を記載した
- [x] pytest 全PASS
- [x] black / isort 全PASS
- [x] routes から Odoo を直接呼んでいない（adapter 経由）
- [x] 境界（routes / adapters / vision / db）を破っていない
- [x] scancheckout_oss_plan.md のスコープ内
- [x] CHANGELOG.md 更新（必要な場合）

## 変更ファイル一覧

| ファイル | 操作 | 内容 |
| --- | --- | --- |
| `services/api/app/pos_adapters/odoo_jsonrpc.py` | 修正 | 例外強化・戻り値型保証・docstring 拡充 |
| `services/api/app/routes/pos.py` | 修正 | mode="pos"→400、raw削除、個別メソッド呼び出し、502/500 正常化 |
| `tests/test_odoo_jsonrpc.py` | 新規 | Adapter 単体テスト 23件 |
| `tests/test_pos_route.py` | 新規 | ルート結合テスト 14件 |
| `tests/conftest.py` | 新規 | sys.path 設定 |

## 実行ログ貼り付け欄

### pytest

```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\GitLab\scancheckout-oss
collected 37 items

tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientAuthenticate::test_authenticate_success PASSED [  2%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientAuthenticate::test_authenticate_odoo_error PASSED [  5%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientAuthenticate::test_authenticate_http_error PASSED [  8%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientAuthenticate::test_authenticate_request_error PASSED [ 10%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientAuthenticate::test_authenticate_missing_uid PASSED [ 13%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientCallKw::test_call_kw_success PASSED [ 16%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientCallKw::test_call_kw_odoo_error PASSED [ 18%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientCallKw::test_call_kw_http_error PASSED [ 21%]
tests/test_odoo_jsonrpc.py::TestOdooJsonRpcClientCallKw::test_call_kw_request_error PASSED [ 24%]
tests/test_odoo_jsonrpc.py::TestResolveProductIdsBySku::test_empty_skus_returns_empty_dict PASSED [ 27%]
tests/test_odoo_jsonrpc.py::TestResolveProductIdsBySku::test_resolve_success PASSED [ 29%]
tests/test_odoo_jsonrpc.py::TestResolveProductIdsBySku::test_resolve_partial_miss PASSED [ 32%]
tests/test_odoo_jsonrpc.py::TestResolveProductIdsBySku::test_resolve_odoo_error_propagates PASSED [ 35%]
tests/test_odoo_jsonrpc.py::TestCreateSaleOrderDraft::test_create_success_returns_int PASSED [ 37%]
tests/test_odoo_jsonrpc.py::TestCreateSaleOrderDraft::test_unknown_sku_raises PASSED [ 40%]
tests/test_odoo_jsonrpc.py::TestCreateSaleOrderDraft::test_create_returns_none_raises PASSED [ 43%]
tests/test_odoo_jsonrpc.py::TestCreateSaleOrderDraft::test_create_returns_invalid_type_raises PASSED [ 45%]
tests/test_odoo_jsonrpc.py::TestConfirmSaleOrder::test_confirm_success PASSED [ 48%]
tests/test_odoo_jsonrpc.py::TestConfirmSaleOrder::test_confirm_odoo_error_propagates PASSED [ 51%]
tests/test_odoo_jsonrpc.py::TestConfirmSaleOrder::test_confirm_unexpected_error_wrapped PASSED [ 54%]
tests/test_odoo_jsonrpc.py::TestCheckout::test_checkout_success PASSED   [ 56%]
tests/test_odoo_jsonrpc.py::TestCheckout::test_checkout_create_failure PASSED [ 59%]
tests/test_odoo_jsonrpc.py::TestCheckout::test_checkout_confirm_failure PASSED [ 62%]
tests/test_pos_route.py::TestCheckoutSaleSuccess::test_returns_200_with_ok PASSED [ 64%]
tests/test_pos_route.py::TestCheckoutSaleSuccess::test_record_id_is_int PASSED [ 67%]
tests/test_pos_route.py::TestCheckoutSaleSuccess::test_raw_field_absent PASSED [ 70%]
tests/test_pos_route.py::TestCheckoutSaleSuccess::test_note_passed_to_adapter PASSED [ 72%]
tests/test_pos_route.py::TestCheckoutSaleSuccess::test_confirm_called_with_so_id PASSED [ 75%]
tests/test_pos_route.py::TestCheckoutModePos::test_pos_mode_returns_400 PASSED [ 78%]
tests/test_pos_route.py::TestCheckoutModePos::test_pos_mode_detail_message PASSED [ 81%]
tests/test_pos_route.py::TestCheckoutModePos::test_pos_mode_adapter_not_called PASSED [ 83%]
tests/test_pos_route.py::TestCheckoutOdooError::test_create_draft_error_returns_502 PASSED [ 86%]
tests/test_pos_route.py::TestCheckoutOdooError::test_confirm_error_returns_502 PASSED [ 89%]
tests/test_pos_route.py::TestCheckoutOdooError::test_502_detail_contains_odoo_error PASSED [ 91%]
tests/test_pos_route.py::TestCheckoutUnexpectedError::test_unexpected_error_returns_500 PASSED [ 94%]
tests/test_pos_route.py::TestCheckoutValidation::test_missing_lines_returns_422 PASSED [ 97%]
tests/test_pos_route.py::TestCheckoutValidation::test_invalid_qty_returns_422 PASSED [100%]

============================= 37 passed in 7.44s ==============================
```

### black / isort

```bash
$ python -m black --check --line-length 88 services/ tests/
All done! 5 files would be left unchanged.

$ python -m isort --check --profile black services/ tests/
(no diff - all files pass)
```

## Git 情報

- ブランチ: feature/odoo-sale-order
- HEAD: 2ca3062cfc40271cccf6828d57267c83e6917aa7
- 計測日時: 2026-02-18
