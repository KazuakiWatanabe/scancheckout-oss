# Changelog

本プロジェクトの変更履歴。  
タグ運用（vMAJOR.MINOR.PATCH）に従い、main へマージする変更は原則ここへ記載する。

---

## [Unreleased]

### Added

- `POST /pos/checkout` エンドポイントが `sale.order` を下書き作成 → `action_confirm` で確定できるようになった（`feature/odoo-sale-order`）
- Odoo Adapter（`OdooJsonRpcClient`）の httpx 例外を `OdooJsonRpcError` に統一し、通信エラー時の原因特定を容易にした
- `resolve_product_ids_by_sku` に空リストガードを追加し、不要な Odoo 呼び出しを排除した
- `sale.order.create` の戻り値型保証（`None` / 非数値を明示エラーにする）を実装した
- `confirm_sale_order` に明示的な例外ハンドリングを追加した
- Adapter 単体テスト 23件・ルート結合テスト 14件を追加した（合計 37件）

### Changed

- `POST /pos/checkout` の `mode="pos"` を HTTP 400 でブロックした（現フェーズ未対応）
- レスポンス形式を `{ok, target, record_id, message}` に固定し、`raw` フィールドを削除した
- `OdooJsonRpcError` が HTTP 502、その他の例外が HTTP 500 として正しく返るようルートのエラーハンドリングを修正した

### Fixed

- TBD

### Security

- TBD

---

## [0.1.0] - YYYY-MM-DD

### Added (0.1.0)

- 初期MVP（画像アップロード→確定→Odoo連携）

### Changed (0.1.0)

- なし

### Fixed (0.1.0)

- なし

### Security (0.1.0)

- なし
