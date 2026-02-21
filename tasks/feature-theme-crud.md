# タスク指示書: Theme CRUD + infer 反映

- 作成日: 2026-02-21
- ブランチ: `feature/theme-crud`
- 目的: Theme 登録と infer 候補制限をMVPで成立させる

## 実装範囲

1. Theme CRUD API を追加する
- `GET /themes`
- `POST /themes`
- `GET /themes/{theme_id}`
- `PUT /themes/{theme_id}`
- `DELETE /themes/{theme_id}`

2. infer に Theme 制限を反映する
- `theme_id` 指定時は `theme.sku_list` で候補を絞る
- `theme_id` 不正時は 404

3. UI に Theme 選択を追加する
- `GET /themes` で select を構築する
- infer 呼び出し時に `theme_id` を送る

4. テストを追加する
- Theme CRUD
- infer の Theme 制限
- 不正 theme_id の 404

## 完了条件

- black / isort / pytest 実行
- evidence 生成
- AGENTS.md / CLAUDE.md / plan の境界ルールを満たす
