"""ヘルスチェック API ルート。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """アプリケーションの稼働状態を返す。"""
    return {"status": "ok"}
