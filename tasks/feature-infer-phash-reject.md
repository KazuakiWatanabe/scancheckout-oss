# タスク指示書: PR-I pHash による類似判定 + Reject（該当なし）対応

- 作成日: 2026-02-23
- ブランチ: `feature/infer-phash-reject`
- 配置先: `tasks/feature-infer-phash-reject.md`
- 目的: 「撮影画像が対象商品か否か」を判別できるようにし、該当なしの場合は候補を出さない

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `plan/product_image_master_plan.md`（画像マスターの正）
- `README*.md`（最新）

スコープ拡張禁止:
- embedding/学習/ONNX導入は本PRではやらない（次PR）
- Odoo商品画像同期もやらない
- フロントFW導入もやらない

---

## 1. 背景 / 問題

現状は master_skus を候補として列挙しているだけで、
「撮影画像がその商品かどうか」の判別ができていない。
そのため誤候補が常に出て UX が崩れる。

そこで **pHash（知覚ハッシュ）** を導入し、
類似度が低い場合は **Reject（該当なし）** として候補を空にする。

---

## 2. 目的（MVP）

- 参照画像（商品画像マスター）に pHash を付与して保存する
- 撮影画像の pHash を計算し、参照画像群とハミング距離比較を行う
- best が閾値を超える（=距離が大きい/スコアが低い）場合、候補を空にする
- infer のレスポンスに `is_match / best_score / threshold` を追加する（後方互換も考慮）

---

## 3. アルゴリズム（MVP）

### 3.1 pHash
- 参照画像・撮影画像ともに pHash を計算
- ハミング距離 `d`（小さいほど近い）

### 3.2 スコア化（例）
- `score = 1.0 - (d / 64.0)`（pHash 64bit 前提）
- `best_score = max(scores)`

### 3.3 Reject 判定
- `best_score < threshold` の場合:
  - `is_match = false`
  - `candidates = []`

threshold は config で変更できるようにする（例: env）。
- 例: `INFER_PHASH_THRESHOLD=0.55`（初期値）

---

## 4. データモデル変更（商品画像マスター）

### 4.1 index.json に phash を追加
`storage/product_images/index.json` の item に以下を追加:

- `phash`（文字列: 16進 or base16 など）

例:
```json
{
  "image_id": "img_...",
  "sku": "ANPAN-001",
  "filename": "img_....jpg",
  "content_type": "image/jpeg",
  "created_at": "...",
  "note": "...",
  "phash": "ff12aa..."
}
```

### 4.2 付与タイミング
- `POST /product-images` 登録時に pHash を計算して index.json に保存する

---

## 5. API/I-F 変更（infer）

### 5.1 infer レスポンス（推奨）
既存の `detections[].candidates` は維持しつつ、ルートに以下を追加（または detections に追加）。

推奨（ルート直下）:
```json
{
  "ok": true,
  "is_match": true,
  "best_score": 0.72,
  "threshold": 0.55,
  "detections": [
    {
      "candidates": [
        { "sku": "ANPAN-001", "score": 0.72 }
      ]
    }
  ]
}
```

Reject 時:
```json
{
  "ok": true,
  "is_match": false,
  "best_score": 0.21,
  "threshold": 0.55,
  "detections": [
    { "candidates": [] }
  ]
}
```

※ 既存UIが `detections[].candidates` しか見ていなくても破壊しない。

---

## 6. 実装範囲

### 6.1 依存追加
- `Pillow`
- `ImageHash`（python-imagehash）

※ 既存の依存管理（pyproject/requirements）に合わせて追加。

### 6.2 変更対象（想定）
- `services/api/app/models/product_image_store.py`
  - 登録時に phash を計算して保存
  - 既存データに phash が無い場合の扱い（遅延計算 or 除外）
- `services/api/app/vision/infer.py`
  - pHash 距離比較 / スコア化 / top_k / reject
- `services/api/app/routes/scans.py`
  - infer 結果に `is_match` 等を含めて返す（設計に応じて）
- `services/api/app/config.py`（または相当）
  - `INFER_PHASH_THRESHOLD` の読み込み
- tests
  - `tests/test_phash.py`（新規）
  - `tests/test_product_image_store_phash.py`（新規 or 更新）
  - `tests/test_infer_phash_reject.py`（新規）

---

## 7. 既存データの移行（最低限）

- index.json の既存 item に `phash` が無い場合は:
  - infer 時にその参照画像はスキップ（MVP）
  - もしくは遅延計算して index.json を更新（可能なら）

どちらにするかは実装の簡潔さ優先で選ぶ。
（推奨: 遅延計算 + 更新。失敗時はスキップ）

---

## 8. UI（任意だが推奨）

- `is_match=false` の場合、「該当なし（撮り直し/手入力）」を表示する
- ただし本PRでUI改修が重い場合は、まず API だけでも可
  - その場合、候補0件になればUI側で自然に「候補なし」表示になるようにする

---

## 9. テスト要件

- phash 計算が安定する（同一画像で同一 hash）
- reject されるケース（全く違う画像）で candidates が空になる
- 近い参照画像がある場合、該当SKUが top1 に来る
- threshold を変えると reject 判定が変わる
- 既存 item に phash が無い場合でも 500 にならない

---

## 10. DoD（完了条件）

- 商品画像登録時に phash が保存される
- infer が pHash 比較で候補をスコア付きで返す
- best_score が閾値未満なら候補0件（Reject）
- black/isort/pytest が通る
- evidence を生成できる

---

## 11. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "feature/infer-phash-reject" --git-ref HEAD
```

---

## 12. Codex への指示（このまま貼り付けて使う）

あなたは ScanCheckout OSS の実装エージェントです。
`tasks/feature-infer-phash-reject.md` を最優先で読み、指示に従って実装してください。

実装開始前に必ず提示：
1) 変更予定ファイル一覧
2) pHash の保存場所（index.json）と移行方針（phash無しの扱い）
3) threshold のデフォルト値と設定方法

実装後に必ず報告：
- 変更ファイル一覧
- 手動確認手順（登録→撮影→reject/accept の確認）
- pytest結果
- evidence生成結果
- plan / AGENTS 違反なし確認
