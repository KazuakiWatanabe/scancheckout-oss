# Pull Request Template

<!--
PR テンプレート（ScanCheckout OSS）
- 1PR = 1責務
- AGENTS.md / CLAUDE.md / scancheckout_oss_plan.md の遵守
-->

## 概要
<!-- 何を変更したかを1〜3行で -->

## 背景 / 目的
<!-- なぜ必要か（課題/要望/計画との対応） -->

## 変更点（要約）

- [ ]
- [ ]

## 影響範囲

- 影響するAPI：
- 影響するDB：
- 影響するUI：
- Odoo連携： sale.order / pos.order / なし

## 動作確認

- [ ] docker compose up で起動
- [ ] API疎通（/health, /pos/checkout 等）
- [ ] UI（該当画面）
- [ ] Odoo（疎通 / レコード作成）

## テスト

- [ ] pytest 実行（全PASS）
- [ ] black / isort 実行（全PASS）

## evidence（証跡）

- [ ] scripts/generate_evidence.py を実行し、生成物を添付 or リンク
- evidence パス：

## 設計方針チェック（AGENTS.md）

- [ ] routes から Odoo を直接呼んでいない（adapter 経由）
- [ ] 境界（routes / adapters / vision / db）を破っていない
- [ ] 日本語 docstring を追加した
- [ ] scancheckout_oss_plan.md のスコープ内

## リリース（必要な場合）

- [ ] CHANGELOG.md を更新した
- [ ] タグ方針（vMAJOR.MINOR.PATCH）に合致
