# 05. シーケンス図

このドキュメントは、現行実装（FastAPI + JSON ストア + Odoo Adapter）の主要処理フローを示します。

## 1. 商品画像登録（`POST /product-images`）

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant R as ProductImagesRoute
  participant S as ProductImageStore
  participant V as EmbeddingVision
  participant E as ProductEmbeddingStore

  C->>R: multipart/form-data (image, sku, note?)
  R->>R: 入力検証 (content_type, size, sku)
  R->>S: create_image(...)
  S->>S: 画像保存 + index.json 更新 + phash計算
  S->>V: compute_embedding_vector(...)
  V-->>S: embedding vector
  S->>E: save_embedding(image_id, vector, model_name)
  E-->>S: 保存完了
  S-->>R: ProductImageRecord
  R-->>C: 201 Created (ok, image_id, sku)
```

## 2. スキャン推論（`POST /scans/{scan_id}/infer`）

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant SR as ScansRoute
  participant SS as ScanStore
  participant PI as ProductImageStore
  participant PE as ProductEmbeddingStore
  participant IF as InferVision

  C->>SR: POST /scans/{scan_id}/infer {top_k, theme_id?}
  SR->>SS: get_scan(scan_id)
  SS-->>SR: scan record
  SR->>PI: list_master_skus(), list_reference_records(...)
  PI-->>SR: 参照画像 + phash
  SR->>PE: get_embeddings(image_ids)
  PE-->>SR: 参照embedding
  SR->>SS: load_image_bytes(scan_id)
  SS-->>SR: scan image bytes
  SR->>IF: infer_with_embedding(...)
  IF->>IF: pHash gate(任意) + cosine類似度 + top_k集約
  IF-->>SR: infer result
  SR->>SS: save_detections(scan_id, detections, model_version)
  SS-->>SR: updated scan record
  SR-->>C: 200 OK (detections, model_id, best_score...)
```

## 3. チェックアウト（`POST /pos/checkout`）

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant PR as PosRoute
  participant AD as OdooJsonRpcAdapter
  participant O as OdooJsonRpc

  C->>PR: POST /pos/checkout (mode, lines, store_id...)
  PR->>PR: 入力検証 + adapter生成
  alt mode == "sale"
    PR->>AD: checkout(CheckoutRequest)
    AD->>O: sale.order.create
    O-->>AD: sale_order_id
    AD->>O: sale.order.action_confirm
    O-->>AD: confirm_result
    AD-->>PR: CheckoutResult(target=sale.order)
  else mode == "pos"
    PR->>AD: create_pos_order_from_ui(...)
    AD->>O: pos.order.sync_from_ui
    O-->>AD: raw result
    AD-->>PR: raw + record_id(抽出)
  end
  PR-->>C: 200 OK (CheckoutOut)
```

## 4. 用語の日本語訳

| 英語 | 日本語訳 |
| --- | --- |
| Client | クライアント |
| Route | ルート（API入口） |
| Store | ストア（永続化管理） |
| Adapter | アダプタ（外部連携窓口） |
| create_image | 画像登録 |
| save_embedding | 埋め込み保存 |
| infer_with_embedding | 埋め込み推論 |
| checkout | 会計登録 |
| scan | スキャン |
| detections | 検出結果 |
