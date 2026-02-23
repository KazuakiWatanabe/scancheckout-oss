# 01. Embedding モデル参照

## 1. 参照論文

- 論文: *Searching for MobileNetV3*
- URL: https://arxiv.org/abs/1905.02244
- 用途: 軽量 CNN バックボーン設計（モバイル/CPU 推論向け）

## 2. 本リポジトリで使用しているモデル

本実装の推論設定は `services/api/app/config.py` に集約されており、既定値は以下です。

- `INFER_MODEL_NAME`: `mobilenetv3-small-224`
- `INFER_MODEL_PATH`: `assets/models/mobilenetv3_small_224.onnx`
- `INFER_MODEL_INPUT_SIZE`: `224`
- 推論ランタイム: `onnxruntime`（`CPUExecutionProvider`）

現在の配置済み ONNX（`services/api/assets/models/mobilenetv3_small_224.onnx`）は、実行時に次の入出力形状で使用されています。

- 入力テンソル: `float32 [batch_size, 3, 224, 224]`
- 出力テンソル: `float32 [batch_size, 1000]`

## 3. 埋め込みとしての扱い

`services/api/app/vision/embedding.py` では、ONNX 出力を 1 次元ベクトルへ reshape し、L2 正規化して Embedding として扱います。

- ベクトル次元: 1000（現在のモデルファイル時点）
- 類似度: cosine similarity
- 推論モデルID: `embedding-onnx-v1`

## 4. 補足

- モデル差し替えは環境変数で可能です（`INFER_MODEL_PATH` 変更）。
- 差し替え時は入力サイズ、出力次元、閾値（`INFER_EMBED_THRESHOLD`）を再調整してください。

## 5. 用語の日本語訳

| 英語 | 日本語訳 |
| --- | --- |
| Embedding | 埋め込み特徴量 |
| model | モデル |
| input tensor | 入力テンソル |
| output tensor | 出力テンソル |
| vector | ベクトル |
| cosine similarity | コサイン類似度 |
| threshold | 閾値 |
| model_id | モデル識別子 |
| batch_size | バッチサイズ |
