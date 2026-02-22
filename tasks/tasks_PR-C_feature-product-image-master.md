# Codex 指示書: PR-C 商品画像マスター API + Storage（MVP / Phase 1）

- 作成日: 2026-02-22
- ブランチ: `feature/product-image-master`
- 配置先: `tasks/feature-product-image-master.md`

---

## 0. 最上位ルール（必読）

- `AGENTS.md`
- `CLAUDE.md`
- `plan/product_image_master_plan.md`（Source of Truth）

**plan の「MVP（Phase 1）」のみ実装**すること。  
非目標（画像比較の本実装、Odoo同期、React/Vite導入、学習基盤など）には触れない。

---

## 1. 目的（MVP）

「比較用の商品画像マスター」をローカル（API側）に登録できるようにする。

- SKU と画像（複数枚）を紐づけて保存
- 一覧取得、画像ファイル取得ができる
- JSON + ローカルファイル保存でOK
- pytest / black / isort が通る

---

## 2. ブランチ運用

- ブランチ作成: `feature/product-image-master`
- タスクファイル作成: `tasks/feature-product-image-master.md`
- PRマージ後: `tasks/done/` に移動（または削除）

---

## 3. 変更対象（想定）

※既存構成に合わせて **最小限**で追加すること。

- `services/api/app/routes/product_images.py`（新規）
- `services/api/app/models/product_image_store.py`（新規）
- `services/api/app/main.py`（router追加）
- `tests/test_product_images_api.py`（新規）
- `tests/test_product_image_store.py`（新規）
- `storage/product_images/`（実行時作成。Git管理しない）

---

## 4. 実装要件（plan 準拠）

### 4.1 登録（アップロード）
- `POST /product-images`
- `multipart/form-data`
  - `image`（必須）
  - `sku`（必須）
  - `note`（任意）

保存要件:
- 保存先: `storage/product_images/<sku>/<image_id>.jpg`
- メタデータ: `storage/product_images/index.json` に追記
- `image_id` は UUID 推奨
- Content-Type 制限（例: image/jpeg, image/png, image/webp）
- サイズ制限（例: 5MB）

レスポンス例:
```json
{
  "ok": true,
  "image_id": "img_...",
  "sku": "SKU-001"
}
```

### 4.2 一覧
- `GET /product-images?sku=SKU-001`
- sku指定ならそのSKUのみ
- 未指定なら全件（将来のページング拡張を阻害しない構造）

### 4.3 取得（画像本体）
- `GET /product-images/{image_id}/file`
- 画像バイナリ返却（正しい Content-Type）

### 4.4 削除（任意）
- `DELETE /product-images/{image_id}`
- index.json から削除し、ファイルも削除
- 失敗時の扱いを明示（例: 片方失敗なら 500 + ログ）

---

## 5. 例外設計

- 不正 Content-Type → 400
- サイズ超過 → 413
- 未存在（image_id / sku）→ 404
- その他 → 500

ログ注意:
- 画像バイナリや個人情報をログ出力しない

---

## 6. セキュリティ（最低限）

- `sku` はパスに使うためサニタイズ（ディレクトリトラバーサル対策）
- ファイル名は生成IDのみ（ユーザー入力は使わない）
- evidence に画像を含めない

---

## 7. テスト要件

- store 単体テスト（index.json の追記/削除/検索）
- API テスト（成功/400/404/413）
- アップロードの Content-Type/サイズ制限が効くこと

---

## 8. 実行コマンド

```bash
black .
isort .
pytest
```

---

## 9. evidence

```bash
python scripts/generate_evidence.py --title "feature/product-image-master" --git-ref HEAD
```

---

## 10. 完了時の出力（Codexが必ず報告）

1. 変更ファイル一覧
2. 追加テスト内容
3. pytest結果
4. evidence生成結果
5. plan / AGENTS 違反がないことの確認
6. 次のPR候補（PR-D: UIに登録タブ追加）
