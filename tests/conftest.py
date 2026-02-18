"""pytest 共通設定。

サービスディレクトリを sys.path に追加し、
routes 層が参照する "app.*" 形式の import を解決する。
"""

from __future__ import annotations

import sys
from pathlib import Path

# services/api を sys.path に追加することで
# "from app.pos_adapters..." 形式の import をテスト環境でも解決する。
_API_ROOT = Path(__file__).parent.parent / "services" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
