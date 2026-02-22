# タスク指示書: PR-D UI に「商品画像マスター登録」タブを追加

- 作成日: 2026-02-22
- ブランチ: `feature/ui-product-image-master`
- 配置先: `tasks/feature-ui-product-image-master.md`
- 前提: PR-C（商品画像マスター API）が main/develop に存在する

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `plan/product_image_master_plan.md`
- `README*.md`（最新）

スコープ拡張禁止（React/Vite導入や、画像比較の本実装はやらない）。

---

## 1. 目的（MVP）

ブラウザ操作UIに「商品画像マスター登録」タブ（またはセクション）を追加し、以下ができるようにする：

- SKU を入力して参照画像をアップロードできる（複数枚）
- アップロード結果（image_id 等）を表示できる
- SKU を指定して画像一覧を取得し、サムネイル表示できる
- クリックで元画像を表示できる（新規タブ or モーダル）

---

## 2. 変更対象（想定）

既存UIが素のHTML/JSである前提。構成に合わせて最小限で変更する。

- `services/api/app/ui/index.html`
- `services/api/app/ui/app.js`
- `services/api/app/ui/styles.css`（必要なら）

※ API ルート/ストア側の変更は原則しない（UIの都合で微調整が必要な場合は最小限）。

---

## 3. UI 仕様（最低限）

### 3.1 タブ構成
- 既存の「スキャン/推論/checkout」操作と並列で、
  「商品画像マスター」タブを追加する（タブUIは簡易でOK）。

### 3.2 登録フォーム
- SKU 入力（必須）
- note（任意）
- 画像ファイル選択（複数）
- 登録ボタン
- 実行中表示（disabled + “Uploading...”）
- 成功/失敗メッセージ表示

アップロード先:
- `POST /product-images`（multipart/form-data）

### 3.3 一覧表示
- SKU フィルタ入力（任意。空なら全件でも良いが件数増に注意）
- `GET /product-images?sku=...`
- 返ってきた image_id を使い、
  `GET /product-images/{image_id}/file` を img src としてサムネイル表示

### 3.4 エラー表示
- HTTP status と message をUIに表示
- 413（サイズ超過）や 400（形式不正）はユーザーに分かる文言にする

---

## 4. 実装ルール

- 日本語コメントを付ける
- UIはFW導入しない（素のJS）
- 画像はUI側で縮小しない（まずはそのまま）
- 個人情報をログ表示しない

---

## 5. DoD（完了条件）

- UIから SKU + 画像（複数枚）が登録できる
- UIでSKU指定の一覧が見られる
- サムネイル/元画像表示ができる
- black/isort/pytest が通る（UI変更でも最低限のlint/既存テストを壊さない）
- evidence を生成できる

---

## 6. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "feature/ui-product-image-master" --git-ref HEAD
```

---

## 7. Codex への指示（このまま貼り付けて使う）

あなたは ScanCheckout OSS の実装エージェントです。
`tasks/feature-ui-product-image-master.md` を最優先で読み、指示に従って実装してください。
`AGENTS.md` / `CLAUDE.md` / plan を必読。スコープ逸脱禁止。

実装は以下の順で進める：
1) 変更予定ファイル一覧と作業手順を提示
2) UIに「商品画像マスター」タブを追加
3) `POST /product-images` を複数画像で呼べるようにする
4) `GET /product-images` + `.../file` で一覧表示
5) エラー表示を整える
6) black/isort/pytest を実行
7) evidence を生成
8) 完了報告（変更ファイル/テスト結果/evidence/次のPR候補）
