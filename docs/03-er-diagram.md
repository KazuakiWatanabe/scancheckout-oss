# 03. ER図（論理モデル）

本プロジェクトは一部を JSON ファイルとインメモリで保持します。  
下図は「実装上の論理エンティティ」を ER として整理したものです。

```mermaid
erDiagram
  THEME {
    string theme_id PK
    string name
    datetime created_at
    datetime updated_at
  }

  THEME_SKU {
    string theme_id FK
    string sku
  }

  SCAN {
    string scan_id PK
    string store_id
    string device_id
    string theme_id FK
    string image_uri
    string content_type
    int size_bytes
    datetime created_at
    string model_version
  }

  SCAN_DETECTION {
    string scan_id FK
    int detection_index
    json bbox
  }

  DETECTION_CANDIDATE {
    string scan_id FK
    int detection_index FK
    int rank
    string sku
    string name
    float score
  }

  PRODUCT_IMAGE {
    string image_id PK
    string sku
    string filename
    string content_type
    datetime created_at
    string note
    string phash
  }

  PRODUCT_EMBEDDING {
    string image_id PK,FK
    string model
    int dim
    json vector
  }

  THEME ||--o{ THEME_SKU : has
  THEME ||--o{ SCAN : selected_by
  SCAN ||--o{ SCAN_DETECTION : stores
  SCAN_DETECTION ||--o{ DETECTION_CANDIDATE : has
  PRODUCT_IMAGE ||--o| PRODUCT_EMBEDDING : has
  PRODUCT_IMAGE }o--o{ THEME_SKU : matched_by_sku
  PRODUCT_IMAGE }o--o{ DETECTION_CANDIDATE : inferred_as_sku
```

## 実体保存先との対応

- `THEME`: `storage/themes/themes.json`
- `PRODUCT_IMAGE`: `storage/product_images/index.json` + 画像ファイル
- `PRODUCT_EMBEDDING`: `storage/product_images/embeddings.json`
- `SCAN` と推論結果: `scan_store` のインメモリ（画像本体のみ `storage/images`）
