# タスク指示書: PR-H Odoo 商品キャッシュ同期（SKU→商品情報）

- 作成日: 2026-02-22
- ブランチ: `feature/odoo-product-cache-sync`
- 配置先: `tasks/feature-odoo-product-cache-sync.md`
- 方針: A案（認識画像はScanCheckout側、販売マスターはOdoo側。SKUで紐づけ）

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `scancheckout_oss_plan.md`（または plan/ 配下の設計書）
- `README*.md`（最新）

境界ルール:
- route から Odoo を直接呼ばない（adapter 経由）
- 既存I/Fを壊さない。差分最小。

---

## 1. 背景

現状は checkout 時に SKU→product_id 解決を行うが、以下が課題：

- Odoo側の商品情報（name/active/price/taxes）を UI で表示できない
- SKU未整備や検索失敗時の診断が難しい
- Odooが遅い/不安定な場合にUI操作が詰まりやすい

そこで、**Odooの商品情報を ScanCheckout 側にキャッシュ**し、
UI/checkout の安定性と可観測性を上げる。

---

## 2. 目的（MVP）

- Odoo から `product.product` を検索し、SKU（default_code）をキーに商品情報を同期する
- 同期結果を `storage/odoo_product_cache.json` に保存する
- UI が候補表示時に「商品名」を表示できるようにする（可能なら）
- checkout は SKU→product_id 解決にキャッシュを優先利用する（可能なら）

---

## 3. キャッシュ仕様（MVP）

保存先:
- `storage/odoo_product_cache.json`

形式（例）:
```json
{
  "version": 1,
  "synced_at": "2026-02-23T00:00:00+09:00",
  "items": {
    "ANPAN-001": {
      "product_id": 123,
      "name": "あんぱん",
      "active": true,
      "barcode": "....",
      "list_price": 150.0
    }
  }
}
```

※ `taxes_id` 等は Phase2（必要になったら）で追加。MVPは最小で良い。

---

## 4. 同期方法（MVP）

### 4.1 ルート（管理用）
- `POST /admin/odoo/sync-products`
- リクエスト（例）:
```json
{
  "limit": 500,
  "updated_since": null
}
```

レスポンス（例）:
```json
{
  "ok": true,
  "count": 123,
  "synced_at": "...."
}
```

### 4.2 Odoo検索（JSON-RPC）

対象モデル:
- `product.product`

検索条件（MVP）:
- `default_code != False`
- `active in [True, False]`（まずは両方でも良いが、基本は active=True を優先）

取得フィールド（MVP）:
- `id`
- `default_code`
- `name`
- `active`
- `barcode`（あれば）
- `list_price`（あれば）

推奨メソッド:
- `search_read(domain, fields, limit, offset)`
- もしくは `search` → `read` でも可

---

## 5. 適用箇所

### 5.1 UI（可能なら）
- candidates 表示時に SKU だけでなく `name` も併記する
- キャッシュに無いSKUは SKUのみ表示（fallback）

### 5.2 checkout（可能なら）
- SKU→product_id の解決をキャッシュ優先にする
- キャッシュに無い場合のみOdoo検索（既存方式）

※ 既存 checkout を壊さないこと（後方互換）。

---

## 6. 変更対象（想定）

- `services/api/app/models/odoo_product_cache.py`（新規）
- `services/api/app/routes/admin_odoo.py`（新規 or 既存に追加）
- `services/api/app/pos_adapters/odoo_jsonrpc.py`（必要なら最小限）
- `services/api/app/routes/scans.py`（UI用のname付与をするなら）
- `tests/test_odoo_product_cache.py`（新規）
- `tests/test_admin_odoo_sync_products.py`（新規）

---

## 7. セキュリティ/運用

- 管理用エンドポイントは **無防備に公開しない**
  - MVPでは「開発環境のみ有効」または「簡易トークン」でガード
  - 既存の設定方針があるならそれに合わせる
- Odoo接続情報は環境変数のみ（ログに出さない）
- キャッシュファイルは Git 管理しない（storage配下）

---

## 8. テスト要件

- cache の read/write（ファイルI/O）の単体テスト
- sync ルートのテスト（Odoo client を mock）
- SKUが空/None の商品は除外される
- 同一SKUが複数ある場合の扱い（後勝ち or 例外）を明示し、テストする

---

## 9. DoD（完了条件）

- `POST /admin/odoo/sync-products` でキャッシュが生成される
- キャッシュファイルが想定形式で保存される
- UI候補に商品名が併記される（可能なら）
- pytest / black / isort が通る
- evidence が生成できる

---

## 10. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "feature/odoo-product-cache-sync" --git-ref HEAD
```

---

## 11. Codex への指示（このまま貼り付けて使う）

あなたは ScanCheckout OSS の実装エージェントです。
`tasks/feature-odoo-product-cache-sync.md` を最優先で読み、指示に従って実装してください。

実装開始前に必ず提示：
1) 変更予定ファイル一覧
2) 同期フロー（Odoo→cache.json→UI/checkout適用）
3) セキュリティ（管理APIのガード方法）

実装後に必ず報告：
- 変更ファイル一覧
- 手動確認手順（curl例を含む）
- pytest結果
- evidence生成結果
- plan / AGENTS 違反なし確認
