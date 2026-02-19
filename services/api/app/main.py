"""ScanCheckout API アプリケーション エントリポイント。

uvicorn から `app.main:app` として参照される。

登録ルーター
- /health: 稼働確認
- /scans: 画像アップロード・候補提示
- /pos : チェックアウト関連エンドポイント
"""

from __future__ import annotations

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.pos import router as pos_router
from app.routes.scans import router as scans_router

# FastAPI アプリケーションインスタンス。
app = FastAPI(
    title="ScanCheckout API",
    description="画像スキャン → 候補提示 → Odoo 登録 の業務ループを支える API。",
    version="0.1.0",
)

# ルーターを登録する。
app.include_router(health_router)
app.include_router(scans_router)
app.include_router(pos_router)
