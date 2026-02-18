# ScanCheckout OSS ― Claude Code 最上位ルール（CLAUDE.md）

本ドキュメントは Claude Code が遵守する最上位ルールである。  
**AGENTS.md と scancheckout_oss_plan.md を常に参照**し、違反しない。

---

## 1. 作業前の必須確認

Claude Code は実装前に以下を必ず確認する：

- `scancheckout_oss_plan.md` のスコープ内か
- Odoo連携は `sale.order` から着手しているか
- 境界（routes / pos_adapters / vision）を破っていないか

不明点がある場合、実装を始める前に質問する。

---

## 2. Claude Code 固有ルール（Memory活用）

Claude Code は、作業効率と一貫性のために Memory を活用する。  
参照：[Claude Code Memory ドキュメント](https://code.claude.com/docs/ja/memory)

Memory に保存すべき優先事項：

- 設計意図（「候補提示＋人補正＋データ蓄積」優先）
- 制約（境界分離、外部送信禁止、版差注意）
- ブランチ戦略（main直push禁止、PR必須）
- 直近の差分（どこまで実装したか、どのTODOが残っているか）

Memory 運用ルール：

- 長期に効く「不変の原則」だけを保存する
- 一時的なログ（大量のコマンド出力、個人情報、秘密情報）は保存しない
- 設計が更新されたら Memory も更新する（古い前提を残さない）

---

## 3. Claude Code の作業手順（推奨）

1) 影響ファイル一覧を先に提示  
2) 変更を小さく分割（1PR = 1責務）  
3) black / isort / pytest を実行  
4) evidence を生成し、PRに添付できる状態にする  
5) `CHANGELOG.md` を更新（必要な場合）

---

## 4. 完了条件（必須）

- pytest PASS
- evidence 保存（`scripts/generate_evidence.py` を使用）
- black/isort 適用
- 日本語 docstring 記載
- AGENTS.md 違反なし

---

## 5. Git運用（Claude Code用）

Claude は以下ブランチのみ作成可能：

- feature/odoo-*
- feature/ui-*
- feature/vision-*
- fix/*
- docs/*

main 直接編集は禁止。

---

## 6. Odoo実装時の特別注意

- `create_from_ui` は **必ず payload 検証前提**（Odoo版差が大きい）
- SKU→product_id 解決を adapter 内に隠蔽する
- Odoo の `call_kw` 直接利用は adapter 内のみ

---

## 7. ScanCheckout思想

このプロジェクトの成功は以下：

- 完全自動認識ではない
- 現場が速く確定できる UI
- データが溜まる設計（学習の種）

Claude Code は「精度改善」より「ループ完成」を優先する。

---

## 8. タグ運用（リリース）

- タグ形式：`vMAJOR.MINOR.PATCH`
- main マージ時にタグ付与
- MINOR：機能追加
- PATCH：バグ修正
- `CHANGELOG.md` 更新必須

---

## 9. 禁止事項

- スコープ拡張
- route 内で Odoo を直接呼ぶ（adapter を経由する）
- テスト未実施
- docstring 未記載
- 版差未確認の `create_from_ui` 実装
