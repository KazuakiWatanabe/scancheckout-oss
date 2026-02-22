# タスク指示書: PR-C 商品画像マスター API + Storage

- 作成日: 2026-02-22
- ブランチ: `feature/product-image-master`
- 目的: SKU と参照画像をローカルで登録・一覧・取得できるようにする

## 実装範囲

1. 商品画像マスター API を追加
- `POST /product-images`
- `GET /product-images`
- `GET /product-images/{image_id}/file`
- `DELETE /product-images/{image_id}`

2. 商品画像ストアを追加
- `storage/product_images/index.json` にメタデータを保存
- `storage/product_images/<sku>/<image_id>.<ext>` に画像保存

3. テスト追加
- store 単体テスト
- API テスト（成功/400/404/413）

## 完了条件

- black / isort / pytest 実行
- evidence 生成
- AGENTS.md / CLAUDE.md / plan のスコープ逸脱がない
