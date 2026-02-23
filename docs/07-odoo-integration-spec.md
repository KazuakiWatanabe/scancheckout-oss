# 07. Odoo連携仕様

本ドキュメントは、ScanCheckout API と Odoo 間の連携仕様を現行実装ベースで定義します。  
対象実装:

- `services/api/app/routes/pos.py`
- `services/api/app/pos_adapters/odoo_jsonrpc.py`

## 1. 連携の責務境界

- `routes` 層: HTTP 入出力、バリデーション、エラーコード変換
- `pos_adapters` 層: Odoo JSON-RPC 呼び出し、payload 組み立て
- 禁止事項: `routes` から Odoo `call_kw` を直接呼ばない

## 2. 連携エンドポイント

## 2.1 API 側入口

- Method: `POST`
- Path: `/pos/checkout`

## 2.2 Odoo 側呼び出しエンドポイント

- 認証: `POST /web/session/authenticate`
- 業務呼び出し: `POST /web/dataset/call_kw`

`call_kw` の `model/method` は処理モードで切り替えます。

## 3. 処理モード

## 3.1 `mode="sale"`（既定）

処理フロー:

1. SKU を `product.product` で解決（`search_read`）
2. `sale.order.create` で下書き受注を作成
3. `sale.order.action_confirm` で確定

利用 Odoo モデル/メソッド:

- `product.product.search_read`
- `sale.order.create`
- `sale.order.action_confirm`

## 3.2 `mode="pos"`

処理フロー:

1. POS セッション存在/状態確認（`pos.session.search_read`）
2. SKU を `product.product` で解決（`search_read`）
3. `pos.order.sync_from_ui` を呼び出し

利用 Odoo モデル/メソッド:

- `pos.session.search_read`
- `product.product.search_read`
- `pos.order.sync_from_ui`

制約:

- 現在は `draft=True` のみ対応
- `draft=False` は未対応（版差が大きいため）

## 4. リクエスト仕様（`/pos/checkout`）

```json
{
  "store_id": "store-a",
  "operator_id": "op-1",
  "mode": "sale",
  "lines": [
    { "sku": "BREAD-001", "qty": 1, "price_unit": 120 }
  ],
  "note": "memo",
  "pos_session_id": 3,
  "partner_id": 1
}
```

主な項目:

- `mode`: `sale` or `pos`
- `lines[].sku`: Odoo 商品解決キー（既定は `default_code`）
- `lines[].qty`: `> 0` 必須
- `lines[].price_unit`: 任意（未指定時は Odoo 既定価格）
- `pos_session_id`: `mode=pos` で必須（未指定時は環境変数 fallback）

## 5. レスポンス仕様（`/pos/checkout`）

```json
{
  "ok": true,
  "target": "sale.order",
  "record_id": 123,
  "raw": {},
  "message": null
}
```

- `target`: `sale.order` または `pos.order`
- `record_id`: 取得できる場合のみ設定
- `raw`: Odoo 応答の生データ（調査用途）

## 6. 環境変数仕様

| 変数名 | 必須 | 既定値 | 用途 |
| --- | --- | --- | --- |
| `ODOO_URL` | Yes | - | Odoo ベース URL |
| `ODOO_DB` | Yes | - | Odoo DB 名 |
| `ODOO_USER` | Yes | - | Odoo ログインユーザー |
| `ODOO_PASSWORD` | Yes | - | Odoo パスワード |
| `POS_ADAPTER` | No | `odoo` | 連携アダプタ種別 |
| `DEFAULT_PARTNER_ID` | No | `1` | 既定顧客ID |
| `DEFAULT_PRICELIST_ID` | No | `None` | 既定価格表ID |
| `DEFAULT_POS_SESSION_ID` | No | `None` | 既定 POS セッションID |
| `CREATE_POS_DRAFT` | No | `true` | POS 注文を下書きで作成 |
| `SKU_FIELD` | No | `default_code` | SKU 解決フィールド |

## 7. SKU 解決仕様

- 検索対象モデル: `product.product`
- 検索メソッド: `search_read`
- 検索条件: `[[SKU_FIELD, "in", skus]]`
- 取得項目: `id`, `SKU_FIELD`, `name`, `lst_price`

SKU 未解決時:

- `sale` モード: `OdooJsonRpcError("Unknown SKU: ...")`
- `pos` モード: 同上

## 8. Odoo payload 仕様（要点）

## 8.1 `sale.order.create` payload

- `partner_id`
- `order_line`: One2many コマンド `(0, 0, vals)` の配列
  - `product_id`
  - `product_uom_qty`
  - `price_unit`（任意）
- `pricelist_id`（任意）
- `note`（任意）

## 8.2 `pos.order.sync_from_ui` payload（1注文）

- `uuid`
- `session_id`
- `state`（`draft`）
- `partner_id`
- `amount_total`, `amount_tax`, `amount_paid`, `amount_return`
- `lines`: `[0, 0, line_vals]` 形式
  - `product_id`, `qty`, `price_unit`, `discount`
  - `price_subtotal`, `price_subtotal_incl`, `tax_ids`

注記:

- `sync_from_ui` payload は Odoo 版差・導入モジュール差の影響を受けます。
- 実運用では POS 実画面の Network payload と合わせて調整してください。

## 9. エラーマッピング

| 事象 | API ステータス | detail |
| --- | --- | --- |
| 未対応 `POS_ADAPTER` | `400` | 未対応のアダプタ |
| `mode=pos` で session 未確定 | `400` | `pos_session_id` 必須 |
| Odoo JSON-RPC エラー | `502` | `Odoo エラー: ...` |
| 想定外例外 | `500` | 例外メッセージ |

## 10. Odoo 側前提条件

- `Sales` アプリ導入済み（`sale` モード）
- 商品が `product.product` に登録済み
- SKU（既定 `default_code`）が API 入力と一致
- `pos` モード時は有効な `pos.session` が存在し、`closed` でない

## 11. 現在の実装方針

- MVP は `sale` モードを主経路とする
- `pos` モードは `sync_from_ui` ベースで提供
- `create_from_ui` 直接実装は未採用（版差検証を優先）
