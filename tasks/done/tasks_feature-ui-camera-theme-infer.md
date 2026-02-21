# タスク指示書: UI（カメラ/撮影）＋テーマ管理＋仮推論（候補提示）

- 作成日: 2026-02-21
- 対象: ScanCheckout OSS
- 目的: 操作用UI・カメラ撮影・テーマ登録・仮推論で「業務ループ」を回す

---

## 0. 最上位ルール（必読）

実装は必ず以下に従う：
- `AGENTS.md`
- `CLAUDE.md`
- `scancheckout_oss_plan.md`（※名称が異なる場合は plan ファイル）
- `README*.md`（最新）

特に境界ルール：
- route から Odoo を直接呼ばない（adapter 経由）
- vision は外部APIに直接依存しない

---

## 1. 背景と目的

現状は API の骨組みがあり、次に「実際に操作できる」状態へ進める。

### 目的（MVPの業務ループ）
1) 操作用UIを用意する（ブラウザで開ける）  
2) カメラを起動し、撮影して画像をAPIへ送れる  
3) 画像から「候補SKU」を表示し、人が確定できる  
4) 確定した明細を `/pos/checkout`（mode="sale"）で Odoo に登録できる  
5) 「認識テーマ（Theme）」を登録し、候補を絞り込める  

---

## 2. 推論のタイミング（重要）

推論の「本実装」は **UIでループが回ってから**入れる。

### 今回（Phase 1）でやる推論
- **仮推論（ルールベース/ダミー）**
- 入力：画像（受け取り・保存は既存方針に従う）
- 出力：`theme.sku_list` を候補集合として `top_k` を返す
  - 例：登録順 / ランダム / 最頻度（簡易）

> 候補が出れば UI の検証が進む。精度改善は後回し。

### 次（Phase 2）以降で入れる推論
- ONNX/TFLite などの軽量モデルに差し替え（I/Fは維持）
- データ（画像×確定SKU）が溜まったら精度改善へ

---

## 3. 作業の分割（おすすめPR）

### PR-A: UI 静的配信 + カメラ撮影 + /scans 連携（仮推論まで）
- ブランチ: `feature/ui-camera-scan-infer`
- ゴール: ブラウザで撮影→API送信→候補表示→確定→/pos/checkout まで通す

### PR-B: Theme CRUD + infer で theme 反映
- ブランチ: `feature/theme-crud`
- ゴール: theme を登録し、候補集合が theme により変わる

---

## 4. 実装方針（UI）

UI はまず素の HTML/JS で良い（React/Vite は後）。

推奨配置:
- `services/api/app/ui/index.html`
- `services/api/app/ui/app.js`
- `services/api/app/ui/styles.css`

UIフロー:
1. カメラ開始（getUserMedia）
2. 撮影（video → canvas → Blob）
3. `POST /scans`（multipart/form-data）
4. `POST /scans/{scan_id}/infer`（json: top_k + theme_id）
5. 候補表示 → ユーザーが SKU と数量を確定
6. `POST /pos/checkout`（mode="sale"）
7. 結果表示（ok / record_id / message）

---

## 5. 実装方針（Theme）

MVP定義：Theme = 「候補SKUの集合」

必要API（例）:
- `GET /themes`
- `POST /themes`
- `GET /themes/{theme_id}`
- `PUT /themes/{theme_id}`
- `DELETE /themes/{theme_id}`

永続化は最初は JSON ファイルでも可（plan に従う）。

---

## 6. DoD（完了条件）

- UI で「撮影→候補表示→確定→Odoo登録」まで操作できる
- Theme を登録でき、候補の絞り込みが動く
- black/isort/pytest が通る
- evidence を生成できる

---

## 7. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "ui-camera-theme" --git-ref HEAD
```

---

## 8. Codex への指示（このまま貼り付けて使う）

### 8.1 共通ルール
- `AGENTS.md` / `CLAUDE.md` / plan / README を必読し、遵守すること
- スコープ拡張禁止（React導入・本推論・学習基盤などは今回やらない）
- 変更は小さく分割し、PR単位で完結させる

### 8.2 PR-A（UI + カメラ + /scans + 仮推論）指示
目的：ブラウザUIで撮影し、APIへ送信し、候補を表示して確定し、`/pos/checkout` まで通す。

変更対象（想定）:
- `services/api/app/main.py`（static mount 追加など）
- `services/api/app/ui/index.html`
- `services/api/app/ui/app.js`
- `services/api/app/ui/styles.css`
- （必要なら）`services/api/app/routes/scans.py`（入出力I/Fの微調整）
- （必要なら）`services/api/app/vision/*`（仮推論の返却を安定させる）

実装要件:
- UI は getUserMedia を使いカメラ開始できる
- 撮影→画像アップロードは multipart/form-data で `/scans` に送る
- infer は `top_k` と `theme_id` を送れる形にする（theme 未実装の場合は None/空でOK）
- 候補をリスト表示し、ユーザーが SKU と数量を確定できる
- 確定後、`/pos/checkout` に mode="sale" でPOSTし、結果を画面表示する
- エラー時は status と message を UI に表示する
- 日本語コメント/説明を付ける（UIコード内も含む）

禁止:
- create_from_ui の実装
- Odoo adapter 境界を壊す変更
- フロントに大規模FW導入

### 8.3 PR-B（Theme CRUD + infer 反映）指示
目的：テーマ登録ができ、infer が theme により候補集合を絞れる。

変更対象（想定）:
- `services/api/app/routes/themes.py`（新規）
- `services/api/app/models/theme_store.py`（新規）
- `services/api/app/routes/scans.py`（theme_id を保存/参照）
- UI（theme選択UIを軽く追加）

実装要件:
- Theme の CRUD が動く
- UI から Theme を選べる（select でOK）
- infer は theme の sku_list に候補を制限し top_k 返す

---

## 9. tasks/ 運用（このファイルの扱い）

- ブランチ作成時に `tasks/` にタスクMDを作成する
- PRマージ後は `tasks/done/` に移動する（または削除）
- 命名はブランチ名に揃える（例：`tasks/feature-ui-camera-scan-infer.md`）
