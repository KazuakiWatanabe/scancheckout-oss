"""evidence（証跡）テンプレ自動生成スクリプト。

目的
- PR作成時に必要な「証跡」を最短で揃える。
- 生成物を evidence/ 配下に集約し、レビュー時に参照しやすくする。

生成するもの（例）
- evidence/README.md : 証跡インデックス
- evidence/checklist.md : PRのDoDチェックリスト
- evidence/meta.txt : メタ情報（自動生成）

使い方
python scripts/generate_evidence.py --title "feature/odoo-sale-order" --git-ref HEAD

注意
- secrets を含めない（.env は基本出力しない、必要ならマスクする）
- 画像や顧客情報など個人情報は保存しない
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--title",
        required=True,
        help="evidence のタイトル（例: feature/odoo-sale-order）",
    )
    parser.add_argument(
        "--git-ref",
        default="HEAD",
        help="対象の git ref（既定: HEAD）",
    )
    parser.add_argument(
        "--out",
        default="evidence",
        help="出力先ディレクトリ（既定: evidence）",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    (out_dir / "README.md").write_text(
        f"""# Evidence

- タイトル: {args.title}
- 作成日時: {now}
- Git ref: {args.git_ref}

## 生成物
- checklist.md : DoDチェックリスト
- meta.txt : メタ情報（自動生成）

## 手動で追加するもの（推奨）
- pytest の実行結果（貼り付け/スクリーンショット/ログ）
- black/isort の実行結果
- API疎通結果（curl など）
- UI動作確認のスクリーンショット
""".rstrip()
        + "\n",
        encoding="utf-8",
    )

    (out_dir / "checklist.md").write_text(
        """# DoD チェックリスト（PR 添付用）

- [ ] 日本語 docstring を記載した
- [ ] pytest 全PASS
- [ ] black / isort 全PASS
- [ ] routes から Odoo を直接呼んでいない（adapter 経由）
- [ ] 境界（routes / adapters / vision / db）を破っていない
- [ ] scancheckout_oss_plan.md のスコープ内
- [ ] CHANGELOG.md 更新（必要な場合）

## 実行ログ貼り付け欄

### pytest
```
（ここに貼る）
```

### black / isort
```
（ここに貼る）
```
""".rstrip()
        + "\n",
        encoding="utf-8",
    )

    (out_dir / "meta.txt").write_text(
        f"""title={args.title}
created_at={now}
git_ref={args.git_ref}
""".rstrip()
        + "\n",
        encoding="utf-8",
    )

    print(f"[OK] Evidence generated at: {out_dir}")


if __name__ == "__main__":
    main()
