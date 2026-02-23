# 06. API仕様書

本仕様は `services/api/app/routes/*.py` の現行実装に基づきます。

## 1. 基本情報

- Base URL（ローカル）: `http://localhost:8000`
- Content-Type:
  - 画像アップロード系: `multipart/form-data`
  - それ以外: `application/json`
- 認証: 現時点では未実装（認証ヘッダ不要）

## 2. 共通エラー形式

FastAPI 標準形式:

```json
{
  "detail": "エラーメッセージ"
}
```

バリデーションエラー時:

```json
{
  "detail": [
    {
      "loc": ["body", "field"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

## 3. エンドポイント一覧

| Method | Path | 概要 |
| --- | --- | --- |
| GET | `/health` | ヘルスチェック |
| POST | `/product-images` | 商品画像の登録 |
| GET | `/product-images` | 商品画像一覧取得 |
| GET | `/product-images/{image_id}/file` | 商品画像ファイル取得 |
| DELETE | `/product-images/{image_id}` | 商品画像削除 |
| GET | `/themes` | Theme 一覧 |
| POST | `/themes` | Theme 作成 |
| GET | `/themes/{theme_id}` | Theme 取得 |
| PUT | `/themes/{theme_id}` | Theme 更新 |
| DELETE | `/themes/{theme_id}` | Theme 削除 |
| POST | `/scans` | スキャン画像登録 |
| POST | `/scans/{scan_id}/infer` | 推論実行 |
| POST | `/pos/checkout` | Odoo へチェックアウト登録 |

## 4. 詳細仕様

## 4.1 GET `/health`

### Response `200`

```json
{
  "status": "ok"
}
```

## 4.2 POST `/product-images`

商品画像を SKU に紐づけて登録します。

### Request（multipart/form-data）

- `image` (file, required)
- `sku` (string, required)
- `note` (string, optional)

制約:

- `image.content_type` は `image/jpeg | image/png | image/webp`
- サイズ上限: 5MB
- `sku` は `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`

### Response `201`

```json
{
  "ok": true,
  "image_id": "uuid",
  "sku": "BREAD-001"
}
```

### Error

- `400`: 入力不正（content_type, sku, 空ファイル等）
- `413`: サイズ超過
- `500`: Embedding 計算失敗など

## 4.3 GET `/product-images`

### Query

- `sku` (string, optional)

### Response `200`

```json
[
  {
    "image_id": "uuid",
    "sku": "BREAD-001",
    "filename": "uuid.jpg",
    "content_type": "image/jpeg",
    "created_at": "2026-02-23T00:00:00+00:00",
    "note": "正面"
  }
]
```

### Error

- `400`: sku 形式不正
- `404`: sku 指定時に該当なし

## 4.4 GET `/product-images/{image_id}/file`

画像ファイル本体を返します。

### Response `200`

- Body: バイナリ
- Content-Type: 画像の MIME type

### Error

- `404`: image_id 不在 / 画像ファイル不在

## 4.5 DELETE `/product-images/{image_id}`

### Response `200`

```json
{
  "ok": true,
  "image_id": "uuid"
}
```

### Error

- `404`: image_id 不在

## 4.6 Theme API

## 4.6.1 POST `/themes`

### Request

```json
{
  "name": "bakery",
  "sku_list": ["BREAD-001", "CAKE-001"]
}
```

### Response `201`

```json
{
  "theme_id": "uuid",
  "name": "bakery",
  "sku_list": ["BREAD-001", "CAKE-001"],
  "created_at": "2026-02-23T00:00:00+00:00",
  "updated_at": "2026-02-23T00:00:00+00:00"
}
```

### Error

- `422`: name 空文字、sku_list 不正

## 4.6.2 GET `/themes`

### Response `200`

- `ThemeOut[]` を返却。

## 4.6.3 GET `/themes/{theme_id}`

### Response `200`

- `ThemeOut` を返却。

### Error

- `404`: theme_id 不在

## 4.6.4 PUT `/themes/{theme_id}`

### Request

- `POST /themes` と同一形式。

### Response `200`

- 更新後の `ThemeOut`。

### Error

- `404`: theme_id 不在

## 4.6.5 DELETE `/themes/{theme_id}`

### Response `200`

```json
{
  "ok": true,
  "theme_id": "uuid"
}
```

### Error

- `404`: theme_id 不在

## 4.7 POST `/scans`

スキャン画像を登録して `scan_id` を発行します。

### Request（multipart/form-data）

- `image` (file, required)
- `store_id` (string, required)
- `device_id` (string, optional)
- `theme_id` (string, optional)

制約:

- `image.content_type` は `image/*`
- サイズ上限: 10MB
- `theme_id` 指定時は存在確認あり

### Response `200`

```json
{
  "scan_id": "uuid",
  "store_id": "store-a",
  "device_id": "device-1",
  "theme_id": "theme-uuid",
  "image_uri": "/app/storage/images/uuid.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 12345,
  "created_at": "2026-02-23T00:00:00+00:00"
}
```

### Error

- `400`: 画像入力不正
- `404`: theme_id 不在
- `413`: サイズ超過

## 4.8 POST `/scans/{scan_id}/infer`

Embedding 類似度で候補を返します。

### Request

```json
{
  "top_k": 3,
  "theme_id": "optional-theme-id"
}
```

制約:

- `top_k`: `1..5`
- `theme_id` 指定時は scan の theme を上書き

### Response `200`

```json
{
  "scan_id": "uuid",
  "model_version": "embedding-onnx-v1",
  "model_id": "embedding-onnx-v1",
  "is_match": true,
  "best_score": 0.92,
  "threshold": 0.65,
  "detections": [
    {
      "bbox": [0.0, 0.0, 1.0, 1.0],
      "candidates": [
        {"sku": "BREAD-001", "name": "BREAD-001", "score": 0.92}
      ]
    }
  ]
}
```

### Error

- `404`: scan_id / theme_id 不在
- `500`: Embedding モデルエラー、embeddings ストア破損

## 4.9 POST `/pos/checkout`

Odoo へ `sale.order` または `pos.order` を登録します。

### Request

```json
{
  "store_id": "store-a",
  "operator_id": "op-1",
  "mode": "sale",
  "lines": [
    {"sku": "BREAD-001", "qty": 1, "price_unit": 120}
  ],
  "note": "memo",
  "pos_session_id": 3,
  "partner_id": 1
}
```

### Response `200`

```json
{
  "ok": true,
  "target": "sale.order",
  "record_id": 123,
  "raw": {},
  "message": null
}
```

### Error

- `400`: mode=pos で `pos_session_id` 未指定、未対応 POS_ADAPTER
- `502`: Odoo 側エラー（JSON-RPC）
- `500`: その他予期しないエラー

## 5. 用語の日本語訳

## 5.1 API 用語

| 英語 | 日本語訳 |
| --- | --- |
| Method | HTTPメソッド |
| Path | パス |
| Request | リクエスト |
| Response | レスポンス |
| Error | エラー |
| Query | クエリパラメータ |
| Body | 本文（ボディ） |
| Content-Type | コンテントタイプ |
| detail | 詳細メッセージ |
| field | 項目 |

## 5.2 主なフィールド名

| 英語名 | 日本語訳 |
| --- | --- |
| scan_id | スキャンID |
| image_id | 画像ID |
| theme_id | テーマID |
| store_id | 店舗ID |
| device_id | 端末ID |
| operator_id | 操作者ID |
| sku | 商品管理コード |
| qty | 数量 |
| price_unit | 単価 |
| image_uri | 画像保存先URI |
| content_type | コンテントタイプ（MIME種別） |
| size_bytes | サイズ（バイト） |
| created_at | 作成日時 |
| updated_at | 更新日時 |
| top_k | 上位候補件数 |
| threshold | 閾値 |
| is_match | 一致判定 |
| best_score | 最高スコア |
| detections | 検出結果 |
| candidates | 候補一覧 |
| bbox | バウンディングボックス（検出領域） |
| score | 類似度スコア |
| model_id | モデル識別子 |
| model_version | モデルバージョン |
