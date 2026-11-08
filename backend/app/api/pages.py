"""API /pages/process + /chapters (contract doc 02 §3).

Contract `/pages/process`:
- Request multipart: `image` (file bytes) + metadata
  (lang_src, series, chapter, page_index, image_url, hash — service worker
  tính sha256; backend tính lại nếu thiếu/không hợp lệ).
- Response: `page_id`, `size`, `regions[]`, `patches[]`, `timing_ms`.
- Cache theo `sha256 + lang_src + pipeline_ver` (doc 02 §4): có cache → trả
  ngay, patch PNG nạp lại từ đĩa rồi b64.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import get_or_create_chapter, get_page, put_page
from app.pipeline.orchestrate import PIPELINE_VER, PagePipeline
from app.pipeline.types import PageResult, Region

router = APIRouter()

_pipeline = PagePipeline()


class _ChapterReq(BaseModel):
    series: str
    chapter: str | None = None
    url: str | None = None


def _decode_image(data: bytes) -> np.ndarray:
    """Decode ảnh từ bytes — không dùng cv2.imread (tên file Unicode, doc AGENTS)."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    return img


def _bgr_to_hex(bgr) -> str | None:
    if bgr is None:
        return None
    b, g, r = [max(0, min(255, int(v))) for v in bgr]
    return f"#{r:02x}{g:02x}{b:02x}"


def _region_to_json(r: Region) -> dict:
    x1, y1, x2, y2 = r.bbox
    return {
        "id": r.order,
        "order": r.order,
        "bbox": [x1, y1, x2, y2],
        "polygon": r.polygon,
        "src_text": r.src_text,
        "vi_text": r.vi_text,  # M2 mới điền
        "kind": "ocr_low" if not r.src_text else r.kind,
        "score": round(r.score, 4),
        "text_color": _bgr_to_hex(r.text_color),
        "bg_color": _bgr_to_hex(r.bg_color),
        "engine": "rapidocr-rec",
    }


def _result_to_response(page_id: str, img_shape, res: PageResult) -> dict:
    """PageResult → JSON đúng dạng ví dụ doc 02 §3."""
    h, w = img_shape[:2]
    patches = []
    for (bx1, by1, bx2, by2), patch in res.patches:
        ok, buf = cv2.imencode(".png", patch)
        patches.append({
            "bbox": [bx1, by1, bx2, by2],
            # lỗi encode hiếm → chuỗi rỗng, extension tự dùng bbox nền trắng
            "png_b64": base64.b64encode(buf.tobytes()).decode() if ok else "",
        })
    return {
        "page_id": page_id,
        "pipeline_ver": PIPELINE_VER,
        "size": [w, h],
        "regions": [_region_to_json(r) for r in res.regions],
        "patches": patches,
        "timing_ms": res.timing_ms,
        "engine": res.engine,
    }


def _cached_to_response(page_id: str, cached: dict) -> dict:
    """Nạp lại kết quả cache: patch từ đĩa → b64."""
    result = cached["result"]
    for p in result.get("patches", []):
        f = Path(p["file"])
        p.pop("file", None)
        p["png_b64"] = base64.b64encode(f.read_bytes()).decode() if f.exists() else ""
    return {**result, "page_id": page_id, "cached": True}


def _store_patches(result: dict, patches_dir: Path) -> None:
    """Lưu patch PNG ra đĩa; trong result.return_json chỉ giữ đường dẫn."""
    patches_dir.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(result["patches"]):
        f = patches_dir / f"patch-{i}.png"
        f.write_bytes(base64.b64decode(p["png_b64"]))
        p["file"] = str(f)
        del p["png_b64"]


@router.post("/pages/process")
def process_page(
    image: bytes = File(...),
    lang_src: str = Form("en"),
    hash_client: str | None = Form(None, alias="hash"),
    series: str | None = Form(None),
    chapter: str | None = Form(None),
    page_index: int | None = Form(None),
    image_url: str | None = Form(None),
    settings: Settings = Depends(get_settings),
):
    img = _decode_image(image)
    if img is None:
        return JSONResponse(status_code=400,
                            content={"error": "Ảnh không decode được (png/jpg/webp?)"})

    # sha256 từ bytes thật — client chỉ gửi hash để tuỳ chọn; luôn tính lại
    page_id = hashlib.sha256(image).hexdigest()

    cached = get_page(page_id, lang_src, PIPELINE_VER)
    if cached is not None:
        return _cached_to_response(page_id, cached)

    res = _pipeline.process(img)
    result = _result_to_response(page_id, img.shape, res)

    # Cache (doc 02 §4): patch PNG ra đĩa, DB chỉ giữ path
    patches_dir = settings.cache_dir / "pages" / page_id[:16]
    _store_patches(result, patches_dir)
    put_page(page_id, lang_src, PIPELINE_VER, result, str(patches_dir))

    # Trả về b64 — nạp lại từ đĩa (cùng code path với cache hit để tự kiểm chứng)
    return _cached_to_response(page_id, {"result": result, "patches_dir": str(patches_dir)})


@router.post("/chapters")
def chapters(req: _ChapterReq):
    return {"chapter_id": get_or_create_chapter(req.series, req.chapter, req.url)}
