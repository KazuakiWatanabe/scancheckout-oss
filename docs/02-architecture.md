# 02. アーキテクチャ説明

本プロジェクトは `AGENTS.md` の境界分離方針に従い、`routes / pos_adapters / vision / models` を明確に分離します。

## 1. 層ごとの責務

| 層 | 責務 | 代表ファイル |
| --- | --- | --- |
| routes | HTTP 入出力、リクエスト/レスポンス整形 | `services/api/app/routes/*.py` |
| pos_adapters | Odoo JSON-RPC 呼び出しの隠蔽 | `services/api/app/pos_adapters/odoo_jsonrpc.py` |
| vision | 画像特徴量計算・類似度判定 | `services/api/app/vision/*.py` |
| models | ローカル永続化（JSON/ファイル） | `services/api/app/models/*.py` |

## 2. 全体構成図

```mermaid
flowchart LR
  UI[UI / Client] --> API[FastAPI routes]

  API --> SCAN_ROUTE[/scans]
  API --> IMG_ROUTE[/product-images]
  API --> THEME_ROUTE[/themes]
  API --> POS_ROUTE[/pos/checkout]

  SCAN_ROUTE --> VISION[vision/infer.py + embedding.py + phash.py]
  SCAN_ROUTE --> SCAN_STORE[models/scan_store.py]
  SCAN_ROUTE --> IMG_STORE[models/product_image_store.py]
  SCAN_ROUTE --> EMB_STORE[models/product_embedding_store.py]

  IMG_ROUTE --> IMG_STORE
  IMG_STORE --> EMB_STORE

  THEME_ROUTE --> THEME_STORE[models/theme_store.py]

  POS_ROUTE --> POS_ADAPTER[pos_adapters/odoo_jsonrpc.py]
  POS_ADAPTER --> ODOO[(Odoo)]

  SCAN_STORE --> LOCAL[(storage/images)]
  IMG_STORE --> LOCAL_IMG[(storage/product_images/index.json + files)]
  EMB_STORE --> LOCAL_EMB[(storage/product_images/embeddings.json)]
  THEME_STORE --> LOCAL_THEME[(storage/themes/themes.json)]
```

## 3. 主要フロー

## 3.1 商品画像登録（`POST /product-images`）

1. routes が画像を受け取る。
2. models が画像を保存し、`index.json` を更新する。
3. vision で pHash と Embedding を計算する。
4. embeddings を `embeddings.json` に保存する。

## 3.2 推論（`POST /scans/{scan_id}/infer`）

1. scan 画像を読み込む。
2. pHash ゲート（ON/OFF 可）で粗い除外を行う。
3. Embedding を計算し、参照 Embedding と cosine 類似度を計算する。
4. SKU 単位でスコア集約し `top_k` を返す。
5. `best_score < threshold` の場合は Reject（候補 0 件）。

## 3.3 Odoo 登録（`POST /pos/checkout`）

1. routes が入力検証を行う。
2. Odoo 呼び出しは `pos_adapters` に委譲する。
3. `sale.order` 作成または POS 同期を実行する。

## 4. 設計上の制約

- routes から Odoo `call_kw` を直接呼ばない。
- vision は外部 API/Odoo に依存しない。
- 永続化は models に限定する。
