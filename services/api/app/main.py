"""ScanCheckout API アプリケーション エントリポイント。

uvicorn から `app.main:app` として参照される。

登録ルーター
- /health: 稼働確認
- /scans: 画像アップロード・候補提示
- /pos : チェックアウト関連エンドポイント

静的配信
- /ui   : 操作用の最小Web UI（HTML/JS/CSS）
"""

from __future__ import annotations

from pathlib import Path

from app.routes.health import router as health_router
from app.routes.pos import router as pos_router
from app.routes.scans import router as scans_router
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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

# main.py から見た UI 静的ファイル配置ディレクトリ。
UI_DIR = Path(__file__).resolve().parent / "ui"

# 操作用 UI を /ui で公開する（MVP: 静的ファイル配信）。
app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


@app.get("/", include_in_schema=False)
def redirect_root_to_ui() -> RedirectResponse:
    """ルートアクセスを UI へリダイレクトする。"""
    return RedirectResponse(url="/ui/")
