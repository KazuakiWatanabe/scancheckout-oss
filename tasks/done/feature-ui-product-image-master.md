# タスク指示書: PR-D UI 商品画像マスター登録

- 作成日: 2026-02-22
- ブランチ: `feature/ui-product-image-master`
- 目的: UI から商品画像マスターを登録・一覧表示できるようにする

## 実装範囲

1. UI タブ（またはセクション）追加
- 既存スキャン操作と並列で「商品画像マスター」を配置

2. 登録フォーム追加
- SKU（必須）
- note（任意）
- 画像ファイル（複数）
- `POST /product-images` 実行

3. 一覧表示追加
- SKU フィルタ入力（任意）
- `GET /product-images` 実行
- `GET /product-images/{image_id}/file` をサムネイル表示に利用

## 完了条件

- UI から複数画像登録が可能
- UI で一覧・画像表示が可能
- black / isort / pytest / evidence 実行
