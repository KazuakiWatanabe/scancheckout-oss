# 04. テーブル仕様（論理）

本仕様は現行実装（JSON ストア + インメモリ）を「論理テーブル」として定義したものです。

## 1. themes

- 物理保存: `storage/themes/themes.json`
- 主キー: `theme_id`

| カラム | 型 | 必須 | 説明 | 制約 |
| --- | --- | --- | --- | --- |
| theme_id | string(UUID) | Yes | Theme 識別子 | 一意 |
| name | string | Yes | Theme 名 | 空文字不可 |
| sku_list | array[string] | Yes | 許可 SKU 一覧 | 重複非推奨 |
| created_at | datetime(ISO8601) | Yes | 作成日時(UTC) |  |
| updated_at | datetime(ISO8601) | Yes | 更新日時(UTC) |  |

## 2. theme_skus（論理展開）

- 物理保存: `themes.sku_list` を展開した論理テーブル
- 主キー: `(theme_id, sku)`

| カラム | 型 | 必須 | 説明 | 制約 |
| --- | --- | --- | --- | --- |
| theme_id | string(UUID) | Yes | Theme 識別子 | `themes.theme_id` 参照 |
| sku | string | Yes | SKU | 1 Theme 内で一意 |

## 3. product_images

- 物理保存: `storage/product_images/index.json`
- 画像本体: `storage/product_images/<sku>/<filename>`
- 主キー: `image_id`

| カラム | 型 | 必須 | 説明 | 制約 |
| --- | --- | --- | --- | --- |
| image_id | string(UUID) | Yes | 画像識別子 | 一意 |
| sku | string | Yes | 商品 SKU | `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` |
| filename | string | Yes | 保存ファイル名 | `<image_id>.<ext>` |
| content_type | string | Yes | MIME タイプ | `image/jpeg` `image/png` `image/webp` |
| created_at | datetime(ISO8601) | Yes | 登録日時(UTC) |  |
| note | string \| null | No | 補足メモ |  |
| phash | string \| null | No | pHash(16進) | 遅延補完あり |

## 4. product_embeddings

- 物理保存: `storage/product_images/embeddings.json`
- 主キー: `image_id`

| カラム | 型 | 必須 | 説明 | 制約 |
| --- | --- | --- | --- | --- |
| version | int | Yes | 形式バージョン | 既定 `1` |
| model | string | Yes | モデル識別子 | 例 `mobilenetv3-small-224` |
| dim | int | Yes | ベクトル次元 | 現在 `1000` |
| items | object | Yes | `image_id -> vector` の辞書 | `vector` は `list[float]` |

## 5. scans

- 物理保存: インメモリ（`InMemoryScanStore._records`）
- 画像本体: `storage/images/<scan_id>.<ext>`
- 主キー: `scan_id`

| カラム | 型 | 必須 | 説明 | 制約 |
| --- | --- | --- | --- | --- |
| scan_id | string(UUID) | Yes | スキャン識別子 | 一意 |
| store_id | string | Yes | 店舗識別子 | 空文字不可 |
| device_id | string \| null | No | 端末識別子 |  |
| theme_id | string(UUID) \| null | No | 推論時テーマ | `themes.theme_id` 参照 |
| image_uri | string | Yes | 保存画像パス | ローカル絶対パス |
| content_type | string | Yes | MIME タイプ | `image/*` |
| size_bytes | int | Yes | ファイルサイズ | > 0 |
| created_at | datetime(ISO8601) | Yes | 作成日時(UTC) |  |
| detections | array[object] | Yes | 推論結果 | API 返却形式準拠 |
| model_version | string \| null | No | 推論ロジック版 | 例 `embedding-onnx-v1` |

## 6. scan_detections / detection_candidates（論理）

- 物理保存: `scans.detections` のネスト構造

### 6.1 scan_detections

| カラム | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| scan_id | string(UUID) | Yes | 親スキャン |
| detection_index | int | Yes | 検出領域インデックス |
| bbox | array[float] | Yes | `[x1, y1, x2, y2]`（正規化） |

### 6.2 detection_candidates

| カラム | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| scan_id | string(UUID) | Yes | 親スキャン |
| detection_index | int | Yes | 親検出領域 |
| rank | int | Yes | 候補順位 |
| sku | string | Yes | 候補 SKU |
| name | string | Yes | 表示名 |
| score | float | Yes | 類似度スコア（0〜1） |

## 7. テーブル名・カラム名の日本語訳

## 7.1 テーブル名

| 英語名 | 日本語訳 |
| --- | --- |
| themes | テーママスタ |
| theme_skus | テーマSKU対応 |
| product_images | 商品画像マスタ |
| product_embeddings | 商品埋め込みベクトル |
| scans | スキャン履歴 |
| scan_detections | スキャン検出領域 |
| detection_candidates | 検出候補 |

## 7.2 カラム名

| 英語名 | 日本語訳 |
| --- | --- |
| theme_id | テーマID |
| image_id | 画像ID |
| scan_id | スキャンID |
| sku | 商品管理コード |
| sku_list | SKU一覧 |
| filename | ファイル名 |
| content_type | コンテントタイプ（MIME種別） |
| created_at | 作成日時 |
| updated_at | 更新日時 |
| note | 備考 |
| phash | 知覚ハッシュ |
| version | 形式バージョン |
| model | モデル名 |
| dim | 次元数 |
| items | 項目辞書 |
| vector | ベクトル |
| store_id | 店舗ID |
| device_id | 端末ID |
| image_uri | 画像保存先URI |
| size_bytes | サイズ（バイト） |
| detections | 検出結果 |
| model_version | モデルバージョン |
| detection_index | 検出インデックス |
| bbox | バウンディングボックス（検出領域） |
| rank | 候補順位 |
| score | 類似度スコア |
| name | 表示名 |
