"""OCR (doc 03 §4). RapidOCR, CHẾ ĐỘ REC-ONLY vùng đã detect.

QUAN TRỌNG (verified bằng experiment 08/11): RapidOCR corrupt state — sau khi
gọi detection (use_rec=False), rec-only trên CÙNG instance trả rỗng. Vì vậy
class này giữ instance riêng chỉ cho recognition. Muốn detection full page,
dùng RapidOCRDetector (detector.py) — instance khác.

Quy trình per-region: crop -> phóng x2 nếu chữ nhỏ -> xám + tương phản -> rec.
"""
from __future__ import annotations

import numpy as np

from app.pipeline.types import Region


class RapidOCREngine:
    name = "rapidocr-rec"

    def __init__(self, dst_lang: str = "en"):
        from rapidocr import RapidOCR

        self.lang = dst_lang
        # Instance RIÊNG chỉ cho recognition (state corruption, xem docstring)
        self.engine = RapidOCR()

    def _prepare_crop(self, crop: np.ndarray) -> np.ndarray:
        h, w = crop.shape[:2]
        if h < 24 or w < 24:  # chữ nhỏ: phóng x2 như doc 03
            crop = cv2_resize(crop, (w * 2, max(1, h * 2)))
        gray = cv2_gray(crop)
        return _clahe(gray)

    def read_regions(self, img: np.ndarray, regions: list[Region]) -> list[Region]:
        H, W = img.shape[:2]
        for r in regions:
            x1, y1, x2, y2 = r.bbox
            pad = max(2, (y2 - y1) // 10)  # lề nhỏ tránh cắt mép chữ
            crop = img[max(0, y1 - pad):min(H, y2 + pad), max(0, x1 - pad):min(W, x2 + pad)]
            if crop.size == 0:
                continue
            data = self.engine(self._prepare_crop(crop), use_det=False, use_cls=False)
            txts = list(data.txts) if data.txts is not None else []
            scores = list(data.scores) if data.scores is not None else []
            # chữ comic in hoa dễ nhầm I/l/1 — để LLM sửa lỗi hiển nhiên ở bước dịch (doc 03 §4)
            r.src_text = " ".join(t.strip() for t in txts if t and t.strip())
            r.score = float(min(scores)) if scores else 0.0
        return regions


def cv2_resize(img, size):
    import cv2

    return cv2.resize(img, size, interpolation=cv2.INTER_CUBIC)


def cv2_gray(img):
    import cv2

    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _clahe(gray):
    import cv2

    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
