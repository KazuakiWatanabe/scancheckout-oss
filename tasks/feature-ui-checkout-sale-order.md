# タスク指示書: PR-G UIで候補を確定し `/pos/checkout` で Odoo（sale.order）登録まで通す

- 作成日: 2026-02-22
- ブランチ: `feature/ui-checkout-sale-order`
- 配置先: `tasks/feature-ui-checkout-sale-order.md`
- 前提:
  - 候補表示（scan → infer → candidates 表示）が動いていること
  - `/pos/checkout`（mode="sale"）が実装済みであること
  - POS（create_from_ui）は本PRでは触らない（sale.order のみ）

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `scancheckout_oss_plan.md`（または plan/ 配下の設計書）
- `README*.md`（最新）

境界ルール：
- route から Odoo を直接呼ばない（adapter 経由）
- 変更は最小・差分最小。不要なリファクタは禁止。

---

## 1. 目的（MVP）

UI から以下を実現する：

1) 推論候補（SKU）をユーザーが選択できる  
2) 数量（qty）を指定できる（デフォルト 1）  
3) 「会計へ（登録）」で `/pos/checkout` を呼び出せる  
4) 成功時に `sale.order` の `record_id` を画面表示できる  
5) 失敗時に HTTP status と message を分かる形で表示できる  

---

## 2. Odoo 側の前提チェック（最短で通す条件）

次の条件が満たされないと SKU 解決で失敗しやすい：

- Odoo の商品コード（`product.product.default_code`）が、UI の SKU と一致している
- 価格は Odoo の pricelist に任せる（UIから price_unit を固定で送らない）
- 顧客（partner_id）は `/pos/checkout` 側の既定値・テスト顧客で良い

※ 本PRでは「SKUと一致していない場合の高度なマッピング」はやらない（次PR）。

---

## 3. 変更対象（想定）

UI 側が中心。API側は原則変更しない。

- `services/api/app/ui/index.html`
- `services/api/app/ui/app.js`
- `services/api/app/ui/styles.css`（必要なら）

（必要なら最小限）
- `services/api/app/routes/pos.py`（レスポンス形式が未固定なら固定）

---

## 4. UI 仕様（最低限）

### 4.1 候補表示に「選択UI」を追加

- 候補リストに radio（単一選択）または checkbox（複数選択）を付ける
  - MVP は **単一選択（radio）** を推奨
- 候補が 0 件の時は「候補なし」と明示

### 4.2 数量入力

- 選択したSKUに対し、qty入力を表示
- デフォルト 1
- 0以下は送信しない（UIでバリデーション）

### 4.3 Checkout 実行

- ボタン：「会計へ（Odoo登録）」
- 呼び出し：`POST /pos/checkout`
- リクエスト例（最小）:

```json
{
  "store_id": "demo-store",
  "operator_id": "demo-operator",
  "mode": "sale",
  "lines": [
    {
      "sku": "ANPAN-001",
      "qty": 1
    }
  ]
}
```

※ `price_unit` は送らない（Odoo側の価格表に任せる）。
※ 複数明細対応は次PR（MVPは1行でも可）。

### 4.4 レスポンス表示

レスポンス形式（固定を推奨）:

```json
{
  "ok": true,
  "target": "sale.order",
  "record_id": 123,
  "message": null
}
```

- ok=true なら record_id を表示（リンクやURL表示は任意）
- ok=false またはHTTPエラーなら status と message を表示

---

## 5. 例外/UX 要件

- 実行中はボタンを disabled（連打防止）
- 失敗時は次を表示：
  - HTTP status
  - APIレスポンス body（message など）
- 502（Odoo連携失敗）と 400（入力不正）はユーザー向け文言を分ける

---

## 6. テスト（最低限）

UI中心のPRなので、既存 pytest を壊さないことが最優先。

- `pytest` が通ること
- 可能なら API 側の `pos.py` のレスポンス形式固定に対するテストを追加（任意）

---

## 7. DoD（完了条件）

- UI で候補を選び qty を入れて `/pos/checkout` を実行できる
- 成功時に record_id が表示される
- 失敗時に status / message が見える
- black/isort/pytest が通る
- evidence が生成できる

---

## 8. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "feature/ui-checkout-sale-order" --git-ref HEAD
```

---

## 9. Codex への指示（このまま貼り付けて使う）

あなたは ScanCheckout OSS の実装エージェントです。
`tasks/feature-ui-checkout-sale-order.md` を最優先で読み、指示に従って実装してください。

最初に以下を提示してから実装開始：
1) 変更予定ファイル一覧
2) UIの画面遷移/状態（候補選択→qty→checkout→結果）の説明
3) 実装手順

実装後は以下を報告：
- 変更ファイル一覧
- 手動確認手順（UI操作手順）
- pytest結果
- evidence生成結果
- plan / AGENTS 違反なし確認
