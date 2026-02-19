# `feature/docker-local-env` デモ手順（API → Odoo確認）

## 1. 目的
`POST /pos/checkout` の 2 モードを実演し、Odoo 反映まで確認する。

- `mode="sale"`: `sale.order` を作成して確定
- `mode="pos"`: `pos.order` を `draft` 作成（Odoo 19 は `sync_from_ui` 経由）

## 2. 事前条件

1. ルート: `C:\GitLab\scancheckout-oss`
2. コンテナ起動済み:
```powershell
docker compose ps
```
3. API疎通確認:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/openapi.json -Method Get
```
4. デモSKU `TEST-SVC` が Odoo に存在
5. `pos_session_id=1` が利用可能

## 3. `sale` モード デモ

```powershell
$body='{"store_id":"demo-store","operator_id":"demo-op","mode":"sale","lines":[{"sku":"TEST-SVC","qty":1}],"note":"demo-sale"}'
curl.exe -s -H "Content-Type: application/json" -d $body http://localhost:8000/pos/checkout
```

期待値:
- `ok: true`
- `target: "sale.order"`
- `record_id` に受注IDが入る

## 4. Odoo 画面確認（sale）

1. `http://localhost:8069` を開く
2. `Sales` を開く
3. `Orders` 一覧で `record_id` の受注を確認
4. 状態が `Sales Order`（確定）になっていることを確認

## 5. `pos` モード デモ

```powershell
$body='{"store_id":"demo-store","operator_id":"demo-op","mode":"pos","pos_session_id":1,"lines":[{"sku":"TEST-SVC","qty":1}],"note":"demo-pos"}'
curl.exe -s -H "Content-Type: application/json" -d $body http://localhost:8000/pos/checkout
```

期待値:
- `ok: true`
- `target: "pos.order"`
- `record_id` にPOS注文IDが入る

## 6. Odoo 画面確認（pos）

1. `Point of Sale` を開く
2. `Orders` を開く
3. `record_id` の注文を確認
4. 状態が `draft` で作成されていることを確認

## 7. よくあるエラー

- `Unknown SKU`
  - Odoo に SKU が未登録。`product.product.default_code` を確認する。
- `mode='pos' の場合は pos_session_id が必要`
  - リクエストへ `pos_session_id` を渡す。
- `Unknown POS session`
  - Odoo 側で POS セッションを作成する。
- Odoo `500`（認証）
  - DB 未初期化か、`ODOO_DB/ODOO_USER/ODOO_PASSWORD` 不一致。

## 8. 補足

- 現在の `mode="pos"` は `draft=True` 前提。
- POS 完全決済フロー（支払い確定）は次フェーズで対応。
