# ScanCheckout OSS 計画: 商品画像マスター（比較用）登録方式

- 作成日: 2026-02-22
- 対象: ScanCheckout OSS
- 関連: PR-A（UI/カメラ/仮推論）, PR-B（Theme CRUD）
- 目的: 「比較する為の商品マスター画像」を登録・管理し、将来の推論（画像比較/埋め込み）へ繋げる

---

## 0. 背景

現状の推論は `infer.py` のダミーロジックであり、
「商品画像同士を比較する処理」および「比較用の商品画像マスターの登録先」は未実装。

次のフェーズで、比較用の商品画像マスターを登録できる仕組みを追加する。

---

## 1. ゴール（この計画で実現すること）

### 1.1 MVP（Phase 1）
- 商品画像マスターを **ローカル（API側）** に登録できる
- SKU と紐づいた「参照画像（複数枚）」を保存できる
- UI から登録（アップロード）できる
- 登録した画像を一覧・取得できる
- Theme により SKU の集合を絞り込める（既存方針と整合）

### 1.2 将来（Phase 2+）
- 画像マスターから特徴量（埋め込み）を作成し、近傍検索で候補生成
- Odoo 商品画像との同期（任意）
- ローカルLLM/クラウドLLMは「SKU候補の補助」に限定（画像は送らない）

---

## 2. 基本方針（最短で回す）

### 2.1 「登録先」はまずローカル
**理由:**
- Odoo 連携（product.image など）は版差・運用差が大きい
- MVPでは「登録→候補提示→確定→Odoo」ループの検証を優先

### 2.2 画像は SKU に紐づける
- SKU が最小の識別子（Theme とも整合）
- 1 SKU に対して複数の参照画像を持てる

### 2.3 安全・閉域
- 参照画像を外部に送信しない
- evidence に画像や個人情報を含めない

---

## 3. データモデル（MVP）

### 3.1 画像メタデータ（JSON）
保存形式（例）: `storage/product_images/index.json`

```json
{
  "version": 1,
  "items": [
    {
      "image_id": "img_...",
      "sku": "SKU-001",
      "filename": "img_....jpg",
      "content_type": "image/jpeg",
      "created_at": "2026-02-22T00:00:00+09:00",
      "note": "任意（角度/包装違いなど）"
    }
  ]
}
```

### 3.2 画像ファイル
- 保存先（例）: `storage/product_images/<sku>/<image_id>.jpg`
- 画像IDは UUID 推奨

---

## 4. API 仕様（MVP）

### 4.1 登録（アップロード）
- `POST /product-images`
- `multipart/form-data`
  - `image`（必須）
  - `sku`（必須）
  - `note`（任意）

レスポンス（例）:
```json
{
  "ok": true,
  "image_id": "img_...",
  "sku": "SKU-001"
}
```

### 4.2 一覧
- `GET /product-images?sku=SKU-001`
- sku 未指定なら全件（ただしページング推奨）

### 4.3 取得（画像本体）
- `GET /product-images/{image_id}/file`
- `Content-Type: image/*`

### 4.4 削除（任意）
- `DELETE /product-images/{image_id}`

---

## 5. UI（MVP）

### 5.1 画面要件
- SKU 入力欄
- 参照画像アップロード（複数枚）
- 登録結果（一覧表示）
- Theme 選択（既存UIと統合してOK）

UI はまず素の HTML/JS で良い（FW導入は後）。

---

## 6. 推論（Phase 1 ではまだ比較しない）

Phase 1 は「比較」をまだやらない。

- infer は引き続き「固定カタログ + Theme による絞り込み」
- ただし、商品画像マスターが登録されている SKU のみを候補にする拡張は可
  - 例：`candidate_skus = theme_skus ∩ master_skus`

Phase 2 で以下を実装：
- 参照画像の埋め込み生成（ONNX/TFLite）
- 撮影画像の埋め込み生成
- 近傍検索（cosine）で top_k

---

## 7. セキュリティ/運用

- 画像は外部送信禁止（LLM含む）
- アップロード制限（サイズ/拡張子/Content-Type）を入れる
- パス・ファイル名はサニタイズする
- ログに画像バイナリや個人情報を出さない
- evidence に画像を含めない

---

## 8. PR 分割（推奨）

### PR-C: Product Image Master API + Storage
- routes: `routes/product_images.py`
- store: `models/product_image_store.py`
- storage: `storage/product_images/`
- tests: API と store の単体テスト

### PR-D: UI 追加（登録画面）
- `ui/index.html` にタブ追加 or 別ページ追加
- アップロードと一覧表示

---

## 9. DoD（完了条件）

- SKU と画像を登録できる
- 画像一覧が表示できる
- 画像ファイルを取得できる
- black/isort/pytest が通る
- evidence が生成できる

---

## 10. 非目標（この計画ではやらない）

- 画像比較アルゴリズムの本実装（Phase 2 へ）
- Odoo 商品画像同期（Phase 2+ へ）
- React/Vite など大型フロント導入
- 学習基盤/再学習パイプライン
