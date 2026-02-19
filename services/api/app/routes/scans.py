"""スキャン画像アップロード・候補提示 API ルート。

提供エンドポイント
- POST /scans
- POST /scans/{scan_id}/infer

設計方針
- routes 層では HTTP I/O のみを担当する
- 画像やメタ情報の保持は models 層へ委譲する
- 候補生成は vision 層へ委譲する
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.models.scan_store import get_scan_store
from app.vision.infer import MODEL_VERSION, infer_topk_candidates

router = APIRouter(prefix="/scans", tags=["scans"])

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


class ScanCreateOut(BaseModel):
    """`POST /scans` のレスポンスモデル。"""

    # スキャンID（以降の infer 呼び出しキー）。
    scan_id: str
    # 店舗識別子。
    store_id: str
    # 端末識別子（任意）。
    device_id: Optional[str]
    # 保存先画像 URI。
    image_uri: str
    # MIME タイプ。
    content_type: str
    # 保存画像サイズ（byte）。
    size_bytes: int
    # 作成時刻（ISO8601）。
    created_at: str


class InferIn(BaseModel):
    """`POST /scans/{scan_id}/infer` の入力モデル。"""

    # 返却候補数。MVP では 1-5 に制限する。
    top_k: int = Field(3, ge=1, le=5)


class CandidateOut(BaseModel):
    """候補 SKU 1件のレスポンスモデル。"""

    sku: str
    name: str
    score: float


class DetectionOut(BaseModel):
    """検出領域1件のレスポンスモデル。"""

    # 正規化 bbox [x1, y1, x2, y2]。
    bbox: list[float]
    # 領域に対する候補一覧。
    candidates: list[CandidateOut]


class InferOut(BaseModel):
    """`POST /scans/{scan_id}/infer` のレスポンスモデル。"""

    scan_id: str
    model_version: str
    detections: list[DetectionOut]


def _validate_upload_image(upload: UploadFile, image_bytes: bytes) -> None:
    """アップロード画像の最小バリデーションを行う。

    Note:
        - MVP では content_type とサイズのみを検査する。
    """
    if not upload.filename:
        raise HTTPException(status_code=400, detail="filename が空です。")

    content_type = upload.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"画像ファイルのみ受け付けます: {content_type}",
        )

    if not image_bytes:
        raise HTTPException(status_code=400, detail="空ファイルは受け付けません。")

    if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"ファイルサイズ上限超過です（max={MAX_UPLOAD_SIZE_BYTES} bytes）。",
        )


@router.post("", response_model=ScanCreateOut)
def create_scan(
    image: UploadFile = File(...),
    store_id: str = Form(...),
    device_id: Optional[str] = Form(None),
) -> ScanCreateOut:
    """画像を受け取り、scan_id を発行して保存する。"""
    image_bytes = image.file.read()
    _validate_upload_image(upload=image, image_bytes=image_bytes)

    store = get_scan_store()
    record = store.create_scan(
        store_id=store_id,
        device_id=device_id,
        filename=image.filename or "upload.bin",
        content_type=image.content_type or "application/octet-stream",
        image_bytes=image_bytes,
    )
    return ScanCreateOut(
        scan_id=record.scan_id,
        store_id=record.store_id,
        device_id=record.device_id,
        image_uri=record.image_uri,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        created_at=record.created_at.isoformat(),
    )


@router.post("/{scan_id}/infer", response_model=InferOut)
def infer_scan(scan_id: str, body: InferIn) -> InferOut:
    """scan_id に紐づく画像から候補 TopK を返す。"""
    store = get_scan_store()
    record = store.get_scan(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"scan_id が存在しません: {scan_id}")

    image_bytes = store.load_image_bytes(scan_id)
    predictions = infer_topk_candidates(image_bytes=image_bytes, top_k=body.top_k)
    detections = [
        {
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "candidates": [
                {"sku": p.sku, "name": p.name, "score": p.score} for p in predictions
            ],
        }
    ]
    updated = store.save_detections(
        scan_id=scan_id,
        detections=detections,
        model_version=MODEL_VERSION,
    )

    return InferOut(
        scan_id=updated.scan_id,
        model_version=updated.model_version or MODEL_VERSION,
        detections=updated.detections,
    )
