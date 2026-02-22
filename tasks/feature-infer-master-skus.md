# タスク指示書: PR-E infer を master_skus 対応に変更

- 作成日: 2026-02-22
- ブランチ: `feature/infer-master-skus`
- 配置先: `tasks/feature-infer-master-skus.md`
- 前提: PR-C（商品画像マスターAPI）が存在する

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `plan/product_image_master_plan.md`
- `README*.md`

スコープ拡張禁止（画像埋め込み生成、類似度計算、LLM導入はやらない）。
今回の目的は「候補母集団を DUMMY_CATALOG から master_skus に切り替える」こと。

---

## 1. 背景

現状の infer は以下の問題がある：

- 候補母集団が `DUMMY_CATALOG` 固定
- Theme による絞り込みで SKU が一致しない場合、候補が0件になる
- 商品画像マスターに登録した SKU が推論候補に出ない

---

## 2. 目的（MVP）

- 候補母集団を **商品画像マスターに登録された SKU 一覧（master_skus）**にする
- Theme がある場合は `theme_skus ∩ master_skus`
- Theme がない場合は `master_skus`
- 候補は安定順（sorted）で top_k を返す

---

## 3. 変更対象（想定）

- `services/api/app/routes/scans.py`
- `services/api/app/vision/infer.py`
- 必要なら `models/product_image_store.py` に list_master_skus() を追加
- `tests/test_infer.py`（新規 or 更新）

---

## 4. 実装仕様

### 4.1 master_skus 取得

`product_image_store` から以下を取得：

```python
master_skus = store.list_master_skus()
```

### 4.2 allowed_skus ロジック

```
if theme_skus:
    allowed = set(theme_skus) ∩ set(master_skus)
else:
    allowed = set(master_skus)
```

### 4.3 infer 側の変更

現在の DUMMY_CATALOG フィルタ方式を廃止し、

```
catalog = [(sku, sku) for sku in sorted(allowed)]
```

のように SKU ベースで候補生成する。

返却形式は既存の detections フォーマットを維持する。

---

## 5. テスト要件

- master_skus に SKU がある場合、infer で候補が出る
- master_skus が空なら候補は空
- Theme がある場合、積集合のみ候補になる
- top_k が正しく制限される

---

## 6. DoD（完了条件）

- 商品画像マスターに登録した SKU が推論候補に出る
- Theme 絞り込みが正しく動作する
- black/isort/pytest が通る
- evidence を生成できる

---

## 7. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "feature/infer-master-skus" --git-ref HEAD
```

---

## 8. Codex への指示（このまま貼り付けて使う）

あなたは ScanCheckout OSS の実装エージェントです。
`tasks/feature-infer-master-skus.md` を最優先で読み、指示に従って実装してください。

最初に以下を提示してから実装開始：
1) 変更予定ファイル一覧
2) 実装手順
3) 追加テスト内容

実装後は以下を報告：
- 変更ファイル一覧
- pytest結果
- evidence生成結果
- plan / AGENTS 違反なし確認
