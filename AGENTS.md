# ScanCheckout OSS ― 最上位ルール定義書（AGENTS.md）

本ドキュメントは、本リポジトリに関わる **すべてのAI（Codex等）と人間**が遵守すべき最上位ルールである。  
README や設計資料よりも **AGENTS.md を優先**する。

本プロジェクトは `scancheckout_oss_plan.md` に基づいて実装すること。  
スコープ拡張は禁止。

---

## 1. プロジェクトの目的

ScanCheckout OSS は以下を最短で成立させる：

> 画像アップロード → 候補提示 → 人が確定 → Odooへ明細作成

最初のゴールは：

- `sale.order`（下書き）作成
- 必要なら `action_confirm` まで
- 将来 `pos.order.create_from_ui` へ拡張可能

---

## 2. アーキテクチャ原則（境界分離）

必ず以下の境界を守る：

| 層 | 責務 |
| ------ | ------ |
| routes | HTTP I/O（FastAPI ルート） |
| pos_adapters | 外部POS連携（Odoo隠蔽） |
| vision | 推論処理（候補生成） |
| models/db | 永続化（Postgres/MinIO 等） |

禁止：

- route 内で Odoo `call_kw` を直接呼ぶ
- adapter 内で HTTP レスポンス制御を行う
- vision が DB/外部API に直接依存する（必要ならアプリ層を介す）

---

## 3. Odoo連携ポリシー

### フェーズ順（必須）

1. `sale.order` draft 作成
2. `action_confirm`
3. POS `create_from_ui`

MVPでは POS 依存実装を増やさない。  
`create_from_ui` は **版差検証（payload確認）前提** で実装する。

---

## 4. 日本語 docstring 必須ルール

すべての Python ファイルは以下を日本語で記載：

1. ファイルサマリー
2. クラス説明
3. 関数説明
4. 条件付き挙動は Note 明示
5. 主要変数の意味説明

未記載 = 未完成。

---

## 5. コーディング規約

- PEP8
- black / isort 互換（line length = 88）
- import の暗黙依存禁止（循環参照を作らない）
- 外部API呼び出しは adapter 内のみ（route/vision から直接叩かない）
- 例外は握りつぶさず、原因が分かる形で message を残す

---

## 6. Git運用（今回プロジェクト用）

| ブランチ | 役割 |
| ---------- | ------ |
| main | 常に動作可能（compose 起動可能） |
| develop | 次リリース候補（統合ブランチ） |
| feature/odoo-* | Odoo連携 |
| feature/ui-* | UI改善 |
| feature/vision-* | 推論 |
| fix/* | バグ修正 |
| docs/* | ドキュメント |

ルール：

- main への直接 push 禁止
- PR 必須（テンプレートに従う）
- 小さく分割してマージする（巨大PR禁止）

---

## 7. Definition of Done（DoD）

- 日本語 docstring 完備
- pytest 全 PASS
- black / isort 通過
- evidence（証跡）保存（後述のスクリプトを使用）
- `scancheckout_oss_plan.md` に反していない

---

## 8. タグ運用（リリース）

- タグ形式：`vMAJOR.MINOR.PATCH`
- main マージ時にタグを打つ
- 機能追加：MINOR
- バグ修正：PATCH
- `CHANGELOG.md` 更新必須

---

## 9. 禁止事項

- Odoo呼び出しの責務破壊（route直呼びなど）
- 版差確認なしで `create_from_ui` 実装
- 画像外部送信（クラウドLLMへ画像を送らない）
- secrets のコミット
- スコープ無断拡張

---

## 10. 設計の意図

本プロジェクトは

「完全自動認識」ではなく  
「候補提示＋人補正＋データ蓄積」を最優先とする。

最短で動くループを作り、精度は後から上げる。
