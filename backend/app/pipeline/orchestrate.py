"""Orchestrate pipeline M1 (doc 08 M1): detect → OCR → inpaint.

DỊCH (LLM) là M2 — ở đây `vi_text` trả rỗng, `timing_ms.translate` = 0.

Nguyên tắc (doc 02 §6):
- 1 worker duy nhất, đồng bộ — dùng `threading.Lock` (FastAPI chạy endpoint
  sync trong threadpool; lock đảm bảo không 2 trang xử lý song song).
- Lỗi từng tầng không làm hỏng cả trang: OCR lỗi 1 vùng → bỏ qua vùng đó
  (`kind="ocr_low"`); inpaint lỗi → patch là crop gốc, chưa xoá chữ.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from app.config import get_settings
from app.models.registry import ModelRegistry
from app.pipeline.detector import RapidOCRDetector
from app.pipeline.inpaint import _region_bg_color, inpaint_region
from app.pipeline.ocr import RapidOCREngine
from app.pipeline.types import PageResult, Region

# Phiên bản pipeline — đổi khi model/thuật toán đổi → tự vô hiệu cache (doc 02 §6)
PIPELINE_VER = "m1-rapidocr"


def _reading_order(regions: list[Region]) -> None:
    """Gán `order`: hàng trên→dưới, trong hàng phải→trái (thứ tự đọc manga).

    Heuristic M1 (doc 08: "nhận diện sai thứ tự đọc" = rủi ro đã biết, sẽ có
    chế độ chỉnh tay sau): gom regions theo y-center, sai số ~70% chiều cao TB.
    """
    if not regions:
        return
    heights = sorted(r.bbox[3] - r.bbox[1] for r in regions)
    tol = max(20, int(0.7 * heights[len(heights) // 2]))

    keyed = sorted(regions, key=lambda r: (r.bbox[1] + r.bbox[3]) / 2)
    rows: list[list[Region]] = [[keyed[0]]]
    row_y = (keyed[0].bbox[1] + keyed[0].bbox[3]) / 2
    for r in keyed[1:]:
        yc = (r.bbox[1] + r.bbox[3]) / 2
        if abs(yc - row_y) <= tol:
            rows[-1].append(r)
        else:
            rows.append([r])
            row_y = yc
    i = 0
    for row in rows:
        row.sort(key=lambda r: -r.bbox[0])  # phải → trái
        for r in row:
            i += 1
            r.order = i


def estimate_text_color(crop: np.ndarray) -> tuple[int, int, int]:
    """Màu chữ ≈ median của 25% pixel tối nhất trong crop (nền thường sáng hơn)."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    if gray.size == 0 or crop.ndim != 3:
        return (0, 0, 0)
    thresh = np.percentile(gray, 25)
    dark = crop.reshape(-1, crop.shape[2])[gray.reshape(-1) <= thresh]
    if dark.size == 0:
        return (0, 0, 0)
    return tuple(int(v) for v in np.median(dark, axis=0))


class PagePipeline:
    """Pipeline 1 trang — giữ instance detector/OCR lâu dài, 1 worker duy nhất."""

    def __init__(self, settings=None, lang_src: str = "en"):
        self.settings = settings or get_settings()
        self._lock = threading.Lock()
        self._detector: RapidOCRDetector | None = None
        self._ocr: RapidOCREngine | None = None
        self._lang = lang_src

    # Lazy load (doc 07 §3): khởi động backend không nạp model nặng nào
    def _ensure_models(self) -> None:
        if self._detector is None:
            self._detector = RapidOCRDetector(threads=self.settings.intra_op_threads)
            ModelRegistry.shared(self.settings).touch("rapidocr-det", self._detector)
        if self._ocr is None:
            self._ocr = RapidOCREngine(dst_lang=self._lang)
            ModelRegistry.shared(self.settings).touch("rapidocr-rec", self._ocr)

    def _safe_ocr(self, img: np.ndarray, regions: list[Region]) -> None:
        for r in regions:  # lỗi 1 bong bóng → bỏ qua bong bóng đó
            try:
                self._ocr.read_regions(img, [r])
                if not r.src_text:
                    r.kind = "ocr_low"
            except Exception:
                r.src_text = ""
                r.score = 0.0
                r.kind = "ocr_low"

    def process(self, img: np.ndarray) -> PageResult:
        """Pipeline đầy đủ 1 trang (có lock — thứ tự xử lý trang tuần tự)."""
        with self._lock:
            return self._process(img)

    def _process(self, img: np.ndarray) -> PageResult:
        self._ensure_models()
        res = PageResult(
            engine={"detector": "rapidocr", "ocr": "rapidocr-rec", "inpaint": "tier1-2"}
        )

        t0 = time.perf_counter()
        regions = self._detector.detect(img)
        res.timing_ms["detect"] = round((time.perf_counter() - t0) * 1000)

        if not regions:  # trang không chữ (bìa/tranh toàn cảnh) → trả sớm (doc 07 §3b)
            res.timing_ms["ocr"] = res.timing_ms["inpaint"] = 0
            res.timing_ms["translate"] = 0
            return res

        t0 = time.perf_counter()
        self._safe_ocr(img, regions)
        res.timing_ms["ocr"] = round((time.perf_counter() - t0) * 1000)

        _reading_order(regions)

        t0 = time.perf_counter()
        for r in regions:
            x1, y1, x2, y2 = r.bbox
            try:
                patch = inpaint_region(img, r, max_tier=2)
            except Exception:
                patch = img[y1:y2, x1:x2].copy()
            res.patches.append((r.bbox, patch))
            crop = img[y1:y2, x1:x2]
            r.bg_color = _region_bg_color(img, r)
            r.text_color = estimate_text_color(crop)
        res.timing_ms["inpaint"] = round((time.perf_counter() - t0) * 1000)

        res.timing_ms["translate"] = 0
        res.regions = regions
        return res
