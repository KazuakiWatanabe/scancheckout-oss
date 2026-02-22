"""商品画像マスター API ルート。

提供エンドポイント
- POST   /product-images
- GET    /product-images
- GET    /product-images/{image_id}/file
- DELETE /product-images/{image_id}

設計方針
- routes 層は HTTP I/O と入力検証を担当する
- 永続化とファイル管理は models.product_image_store に委譲する
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.models.product_image_store import (
    CONTENT_TYPE_TO_SUFFIX,
    ProductImageRecord,
    get_product_image_store,
    normalize_sku,
)
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/product-images", tags=["product-images"])

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


class ProductImageCreateOut(BaseModel):
    """`POST /product-images` のレスポンスモデル。"""

    ok: bool
    image_id: str
    sku: str


class ProductImageOut(BaseModel):
    """商品画像メタデータのレスポンスモデル。"""

    image_id: str
    sku: str
    filename: str
    content_type: str
    created_at: str
    note: Optional[str]


class ProductImageDeleteOut(BaseModel):
    """`DELETE /product-images/{image_id}` のレスポンスモデル。"""

    ok: bool
    image_id: str


def _to_out(record: ProductImageRecord) -> ProductImageOut:
    """ProductImageRecord を API 返却形式へ変換する。"""
    return ProductImageOut(
        image_id=record.image_id,
        sku=record.sku,
        filename=record.filename,
        content_type=record.content_type,
        created_at=record.created_at.isoformat(),
        note=record.note,
    )


def _validate_image_upload(upload: UploadFile, image_bytes: bytes) -> None:
    """アップロード画像のバリデーションを行う。"""
    if not upload.filename:
        raise HTTPException(status_code=400, detail="filename が空です。")

    content_type = upload.content_type or ""
    if content_type not in CONTENT_TYPE_TO_SUFFIX:
        allowed = ", ".join(sorted(CONTENT_TYPE_TO_SUFFIX))
        raise HTTPException(
            status_code=400,
            detail=f"未対応の Content-Type です: {content_type} (allowed: {allowed})",
        )

    if not image_bytes:
        raise HTTPException(status_code=400, detail="空ファイルは受け付けません。")

    if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"ファイルサイズ上限超過です（max={MAX_UPLOAD_SIZE_BYTES} bytes）。",
        )


@router.post(
    "", response_model=ProductImageCreateOut, status_code=status.HTTP_201_CREATED
)
def create_product_image(
    image: UploadFile = File(...),
    sku: str = Form(...),
    note: Optional[str] = Form(None),
) -> ProductImageCreateOut:
    """SKU に紐づく商品画像を保存する。"""
    image_bytes = image.file.read()
    _validate_image_upload(upload=image, image_bytes=image_bytes)
    try:
        normalized_sku = normalize_sku(sku)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store = get_product_image_store()
    record = store.create_image(
        sku=normalized_sku,
        content_type=image.content_type or "application/octet-stream",
        image_bytes=image_bytes,
        note=note,
    )
    return ProductImageCreateOut(ok=True, image_id=record.image_id, sku=record.sku)


@router.get("", response_model=list[ProductImageOut])
def list_product_images(
    sku: Optional[str] = Query(None, description="SKU で絞り込み（任意）"),
) -> list[ProductImageOut]:
    """商品画像メタデータの一覧を返す。"""
    store = get_product_image_store()
    normalized_sku = None
    if sku is not None:
        try:
            normalized_sku = normalize_sku(sku)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    records = store.list_images(sku=normalized_sku)
    if normalized_sku and not records:
        raise HTTPException(
            status_code=404, detail=f"sku が存在しません: {normalized_sku}"
        )
    return [_to_out(record) for record in records]


@router.get("/{image_id}/file")
def get_product_image_file(image_id: str) -> FileResponse:
    """image_id に対応する画像ファイル本体を返す。"""
    store = get_product_image_store()
    record = store.get_image(image_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"image_id が存在しません: {image_id}"
        )

    image_path = store.get_image_path(image_id)
    if image_path is None or not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"画像ファイルが存在しません: {image_id}",
        )

    # FileResponse は Content-Type を media_type で明示する。
    return FileResponse(
        path=Path(image_path),
        media_type=record.content_type,
        filename=record.filename,
    )


@router.delete("/{image_id}", response_model=ProductImageDeleteOut)
def delete_product_image(image_id: str) -> ProductImageDeleteOut:
    """image_id に対応する商品画像を削除する。"""
    store = get_product_image_store()
    deleted = store.delete_image(image_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"image_id が存在しません: {image_id}"
        )
    return ProductImageDeleteOut(ok=True, image_id=image_id)
