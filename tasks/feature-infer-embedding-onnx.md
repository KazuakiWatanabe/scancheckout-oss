# タスク指示書: PR-J Embedding（ONNX）導入で商品認識精度を上げる

- 作成日: 2026-02-23
- ブランチ: `feature/infer-embedding-onnx`
- 配置先: `tasks/feature-infer-embedding-onnx.md`
- 目的: pHash を「Rejectゲート」にしつつ、Embedding 類似度で候補ランキングを行う

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `plan/product_image_master_plan.md`
- `README*.md`

スコープ拡張禁止:
- 学習/再学習パイプラインは作らない（推論のみ）
- 外部LLMに画像を送らない
- 近傍検索DB（Faiss等）の導入はしない（MVPは総当たり）
- フロントFW導入はしない

---

## 1. 背景 / 問題

pHash は照明/角度/背景に弱く、認識精度に限界がある。
実運用に近づけるため、CNN Embedding を使って類似度で候補を作る。

---

## 2. 目的（MVP）

- 参照画像（商品画像マスター）ごとに Embedding を生成し保存する
- 撮影画像の Embedding を生成し、参照Embeddingと cosine 類似度を計算する
- SKUごとにスコアを集約し top_k 候補を返す
- best_score が threshold 未満なら Reject（候補0件）
- pHash Reject は残す（高速ゲート）
  - ただし Embedding を主判定にする

---

## 3. 方式（MVP）

### 3.1 Embedding モデル
- ONNX Runtime を使用
- まずは軽量で一般的なモデルを採用
  - 候補例: MobileNetV3 / EfficientNet-Lite / ResNet50
- 入力: 224x224 RGB（モデルに合わせる）
- 出力: 1次元ベクトル（例: 512/1024）
- 正規化: L2 normalize を行う（cosine を安定化）

※ モデルファイルは `assets/models/` に置く（Git LFS不要なサイズを優先）。
※ もしサイズが大きい場合は「ダウンロードスクリプト」を用意し、CIではスキップできるようにする。

---

## 4. データ設計

### 4.1 参照Embeddingの保存
- 保存先（例）:
  - `storage/product_images/embeddings.json`（小規模想定）
  - もしくは `storage/product_images/embeddings/<image_id>.npy`

MVP推奨: `embeddings.json`（image_id→list[float] で保存）

例:
```json
{
  "version": 1,
  "model": "mobilenetv3",
  "dim": 1024,
  "items": {
    "img_...": [0.01, 0.02, "...省略..."]
  }
}
```

### 4.2 index.json とのリンク
- `storage/product_images/index.json` の item には `image_id` がある
- embedding は `image_id` をキーに持つ
- 既存の `phash` も維持（Rejectゲート用）

---

## 5. フロー

### 5.1 参照画像登録時
- `POST /product-images` で画像保存
- pHash を計算して index.json に保存（既存）
- **Embedding を計算して embeddings.json に保存**（追加）

※ 速度が気になる場合は Phase2 で「非同期化」する。
MVPは同期でOK（まず正しく動かす）。

### 5.2 infer 時
1) 撮影画像の pHash を計算し、粗い Reject を行う（任意/既存）
2) 撮影画像の Embedding を生成
3) 参照Embedding群と cosine 類似度を計算（総当たり）
4) SKUごとに best を取る（または平均）
5) top_k を返す
6) best_score < threshold なら Reject（候補0件）

---

## 6. 閾値・設定

環境変数（例）:
- `INFER_EMBED_THRESHOLD=0.65`
- `INFER_PHASH_THRESHOLD=0.55`（既存）
- `INFER_PHASH_GATE_ENABLED=true/false`
- `INFER_MODEL_NAME=mobilenetv3`
- `INFER_MODEL_PATH=assets/models/<file>.onnx`

MVPではデフォルトを決めて `config.py` に集約する。

---

## 7. APIレスポンス

既存互換を維持しつつ、以下を拡張：

- `model_id`: `"embedding-onnx-v1"`
- `best_score`: cosine類似度（0〜1想定）
- `threshold`: embed閾値
- `is_match`: best_score >= threshold
- candidates の `score` は cosine類似度にする

---

## 8. 実装範囲

### 8.1 依存追加
- `onnxruntime`
- `numpy`
- `Pillow`（既にあるならそのまま）

### 8.2 変更対象（想定）
- `services/api/app/vision/embedding.py`（新規）
  - モデルロード（キャッシュ）
  - 前処理（resize/normalize）
  - 推論→ベクトル→L2 normalize
- `services/api/app/models/product_embedding_store.py`（新規）
  - embeddings.json の read/write
  - image_id 単位の保存/取得
- `services/api/app/models/product_image_store.py`（更新）
  - 登録時に embedding を生成・保存（image_idに紐づけ）
- `services/api/app/vision/infer.py`（更新）
  - embedding 類似度による候補生成
  - pHash はゲート用途で残す
- `services/api/app/config.py`（更新）
  - 環境変数・デフォルト値
- tests
  - `tests/test_embedding.py`
  - `tests/test_product_embedding_store.py`
  - `tests/test_infer_embedding_reject.py`

---

## 9. テスト要件（MVP）

- 同一画像で embedding が安定（同一モデルならほぼ同じ）
- 参照画像と同一画像を与えたとき top1 が一致する
- 閾値未満の時に Reject される
- embeddings.json が壊れていても 500 を出さずに安全に扱う（読み込みエラーは明示）
- モデルファイルが無い場合は起動時/実行時に分かりやすいエラー

※ CIでモデルファイルを扱えない場合は、embedding部分をモックしてテストする手段を用意する。

---

## 10. DoD（完了条件）

- 商品画像登録時に embedding が保存される
- infer が embedding 類似度で top_k を返す
- best_score が閾値未満なら Reject（候補0件）
- pHash ゲートは ON/OFF できる
- black/isort/pytest が通る
- evidence が生成できる

---

## 11. 実行コマンド

```bash
black .
isort .
pytest
python scripts/generate_evidence.py --title "feature/infer-embedding-onnx" --git-ref HEAD
```

---

## 12. Codex への指示（このまま貼り付けて使う）

あなたは ScanCheckout OSS の実装エージェントです。
`tasks/feature-infer-embedding-onnx.md` を最優先で読み、指示に従って実装してください。

実装開始前に必ず提示：
1) 採用する ONNX モデル（ファイル名/入力サイズ/出力dim）
2) モデルの配置方針（assets/models or download script）
3) embeddings の保存方式（json or npy）
4) 閾値のデフォルト値

実装後に必ず報告：
- 変更ファイル一覧
- 手動確認手順（登録→撮影→top1一致/Reject確認）
- pytest結果
- evidence生成結果
- plan / AGENTS 違反なし確認
