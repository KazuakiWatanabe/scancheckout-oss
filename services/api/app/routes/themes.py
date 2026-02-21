"""Theme CRUD API ルート。

提供エンドポイント
- GET    /themes
- POST   /themes
- GET    /themes/{theme_id}
- PUT    /themes/{theme_id}
- DELETE /themes/{theme_id}

設計方針
- routes 層は HTTP I/O と入力検証を担当する
- 永続化は models.theme_store に委譲する
"""

from __future__ import annotations

from app.models.theme_store import ThemeRecord, get_theme_store
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/themes", tags=["themes"])


def _dedupe_skus_preserve_order(items: list[str]) -> list[str]:
    """SKU 配列の重複を順序維持で除去する。"""
    seen: set[str] = set()
    normalized: list[str] = []
    for sku in items:
        if sku in seen:
            continue
        seen.add(sku)
        normalized.append(sku)
    return normalized


class ThemePayload(BaseModel):
    """Theme 作成・更新で使う入力モデル。"""

    # Theme 表示名。
    name: str = Field(..., description="Theme名（空文字不可）")
    # 候補集合として許可する SKU 一覧。
    sku_list: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Theme 名を検証する。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("name は必須です。空文字は指定できません。")
        return stripped

    @field_validator("sku_list")
    @classmethod
    def validate_sku_list(cls, value: list[str]) -> list[str]:
        """SKU 配列を検証し、重複を除去して返す。"""
        normalized: list[str] = []
        for sku in value:
            stripped = sku.strip()
            if not stripped:
                raise ValueError("sku_list に空文字は指定できません。")
            normalized.append(stripped)
        return _dedupe_skus_preserve_order(normalized)


class ThemeOut(BaseModel):
    """Theme の標準レスポンスモデル。"""

    theme_id: str
    name: str
    sku_list: list[str]
    created_at: str
    updated_at: str


class ThemeDeleteOut(BaseModel):
    """Theme 削除レスポンスモデル。"""

    ok: bool
    theme_id: str


def _to_out(record: ThemeRecord) -> ThemeOut:
    """ThemeRecord を API レスポンス形式へ変換する。"""
    return ThemeOut(
        theme_id=record.theme_id,
        name=record.name,
        sku_list=record.sku_list,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get("", response_model=list[ThemeOut])
def list_themes() -> list[ThemeOut]:
    """Theme 一覧を返す。"""
    store = get_theme_store()
    return [_to_out(record) for record in store.list_themes()]


@router.post("", response_model=ThemeOut, status_code=status.HTTP_201_CREATED)
def create_theme(body: ThemePayload) -> ThemeOut:
    """Theme を新規作成して返す。"""
    store = get_theme_store()
    record = store.create_theme(name=body.name, sku_list=body.sku_list)
    return _to_out(record)


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(theme_id: str) -> ThemeOut:
    """theme_id で Theme を取得する。"""
    store = get_theme_store()
    record = store.get_theme(theme_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"theme_id が存在しません: {theme_id}"
        )
    return _to_out(record)


@router.put("/{theme_id}", response_model=ThemeOut)
def update_theme(theme_id: str, body: ThemePayload) -> ThemeOut:
    """theme_id の Theme を更新して返す。"""
    store = get_theme_store()
    updated = store.update_theme(
        theme_id=theme_id, name=body.name, sku_list=body.sku_list
    )
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"theme_id が存在しません: {theme_id}"
        )
    return _to_out(updated)


@router.delete("/{theme_id}", response_model=ThemeDeleteOut)
def delete_theme(theme_id: str) -> ThemeDeleteOut:
    """theme_id の Theme を削除する。"""
    store = get_theme_store()
    deleted = store.delete_theme(theme_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"theme_id が存在しません: {theme_id}"
        )
    return ThemeDeleteOut(ok=True, theme_id=theme_id)
