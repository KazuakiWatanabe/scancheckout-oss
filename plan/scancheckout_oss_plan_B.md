あなたは ScanCheckout OSS の実装担当です。
次の順序で作業してください：①PR-AをコミットしてPush → ②PR-Bに着手。

# 0. 参照（最優先）
- tasks_feature-ui-camera-theme-infer.md を仕様の正として遵守する
- AGENTS.md / CLAUDE.md / plan（scancheckout_oss_plan.md等）/ README*.md を必読
- 境界ルール遵守：routeからOdooを直接呼ばない（adapter経由）、visionは外部APIに直接依存しない

# 1. まずPR-Aをコミットし、Pushする（PR-Bはその後）
前提：PR-Aは「実装済み・未コミット/未Push」の状態。
以下を実施してPR-Aを確定させる：

(1) 作業ブランチ確認
- ブランチが feature/ui-camera-scan-infer であること（違う場合は現在のブランチ運用に合わせつつ、PR-A相当のブランチであることを確認）

(2) 変更差分の最終確認
- タスクのPR-A要件に反していないこと（UIはHTML/JS、推論I/Fは top_k と theme_id を送れる等）
- 不要ファイルやデバッグログが無いこと

(3) フォーマット/テスト/evidence
- black .
- isort .
- pytest
- python scripts/generate_evidence.py --title "ui-camera-theme" --git-ref HEAD
  （コマンドはタスク指示書に従う）

(4) コミット
- 意味単位でコミット（少なくとも1コミット以上）
- コミットメッセージ例：
  - "PR-A: UI camera + scans + dummy infer wiring"
  - "chore: format + tests + evidence"

(5) Push
- origin に push する

(6) PR-Aのタスクファイル運用
- tasks/ 運用方針に従い、PR-A完了後に tasks/done/ へ移動（または削除）する
  ※この運用はタスク指示書にあるため遵守する

PR-Aのpushが完了したら、PR-Bへ進む。

# 2. PR-Bを実装する（Theme CRUD + infer 反映）
目的：
- Theme登録ができ、infer が theme により候補集合を絞れる
- UIからThemeを選べる（selectでOK）
- infer は theme.sku_list に候補を制限し top_k を返す

ブランチ：
- feature/theme-crud を新規作成して作業

変更対象（想定）：
- services/api/app/routes/themes.py（新規）
- services/api/app/models/theme_store.py（新規）
- services/api/app/routes/scans.py（theme_id を保存/参照）
- UI（theme選択UIを軽く追加）

## 2.1 Theme CRUD
- GET    /themes
- POST   /themes
- GET    /themes/{theme_id}
- PUT    /themes/{theme_id}
- DELETE /themes/{theme_id}

バリデーション（最低限）：
- name: 必須、空文字NG
- sku_list: 配列。空文字要素NG。重複は除去（順序は維持）
- theme_id不正・不存在：404

永続化：
- plan/既存方式に合わせる（最初はJSONファイルでも可、という方針に沿う）

## 2.2 scans.py（theme_id保存/参照 + infer反映）
- /scans 作成（または既存のscan更新）で theme_id を保存できるようにする（nullable可）
- /scans/{scan_id}/infer の入力で theme_id を受ける（既存I/Fに合わせる）
- theme_id がある場合：
  - theme_store から theme を取得。無ければ 404
  - 候補SKU集合を theme.sku_list に制限
  - top_k 件を返す
- theme_id がない場合：
  - 従来どおり（制限なし or 既存ダミー推論の挙動を維持）

※Phase1は「仮推論（ルールベース/ダミー）」であり、精度改善やモデル導入はしない（スコープ拡張禁止）

## 2.3 UI（最小）
- UIは素のHTML/JS方針を維持（大規模FW導入は禁止）
- Theme一覧を取得して select を表示
- 未選択（空）を許可
- 選択した theme_id を infer 呼び出し時に送る（top_k と併せる）
- UIに status と message を表示できる（既存PR-A要件の流儀に合わせる）
- UIコード内も含め日本語コメント/説明を付ける

## 2.4 テスト（必須）
- Theme CRUD のAPIテスト（最低1ケースずつ）
- infer で theme_id を指定したとき、候補が theme.sku_list に制限されること
- 不正theme_idで 404 になること

## 2.5 仕上げ
- black/isort/pytest を通す
- evidence生成
- tasks/運用：PR-B用に tasks/feature-theme-crud.md（または命名規約に沿うファイル）を用意し、マージ後に tasks/done/ へ移動（または削除）
- PR本文用に「変更点サマリ」「動作確認手順」「API例」を短くまとめて出力する