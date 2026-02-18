
# ScanCheckout OSS - Claude Code 実装指示書（Phase1: sale.order）

## 🎯 目的

MVPとして以下を完成させる：

1. `/pos/checkout` が `sale.order` を作成できる
2. `action_confirm` まで実行可能
3. Odoo Adapter 境界を守る
4. pytest が通る
5. evidence を生成できる状態にする

---

## 📚 必ず参照するドキュメント

- AGENTS.md
- CLAUDE.md
- scancheckout_oss_plan.md
- README_scancheckout_enterprise.md

スコープ逸脱は禁止。

---

## 🌿 ブランチ

feature/odoo-sale-order

ブランチ作成時に以下を作成する：

tasks/feature-odoo-sale-order.md

---

## 🧩 実装タスク

### 1️⃣ Odoo Adapter 修正

ファイル：

services/api/app/pos_adapters/odoo_jsonrpc.py

実施内容：

- SKU → product_id 解決処理の例外強化
- sale.order.create の戻り値型保証（int）
- action_confirm の例外処理明示
- 例外は OdooJsonRpcError に統一
- 日本語 docstring 完備

禁止：

- create_from_ui 実装
- 直接 call_kw を route から呼ぶこと

---

### 2️⃣ ルート修正

ファイル：

services/api/app/routes/pos.py

実施内容：

- mode="sale" のみ対応
- mode="pos" は 400 を返却
- OdooJsonRpcError は 502
- その他は 500
- レスポンス形式固定：

{
  "ok": bool,
  "target": "sale.order",
  "record_id": int | null,
  "message": str | null
}

---

### 3️⃣ テスト追加

- Adapter 単体テスト（mock Odoo）
- SKU未存在ケース
- action_confirm失敗ケース
- API成功ケース
- APIエラーケース

---

## 🧪 実行

black .
isort .
pytest

---

## 📦 evidence生成

python scripts/generate_evidence.py \
  --title "feature/odoo-sale-order" \
  --git-ref HEAD

---

## 📌 完了報告形式

1. 変更ファイル一覧
2. 追加テスト内容
3. pytest結果
4. evidence生成結果
5. AGENTS.md違反がないことの確認
6. 次のPR候補

---

## 🛑 禁止事項

- スコープ拡張
- docstring未記載
- 境界破壊
- black違反
- create_from_ui 実装

---

## 🧠 設計優先順位

精度よりも「業務ループ完成」を優先する。
LLM連携やUI改善には触れない。
