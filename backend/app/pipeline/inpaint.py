"""Inpaint theo tầng (doc 05 §1): rẻ nhất đủ tốt trước.

- Tầng 1: fill phẳng bằng màu nền median (bong bóng trắng/đen/xám).
- Tầng 2: cv2.inpaint Telea trên crop nhỏ quanh vùng (nền gradient/screentone thưa).
- Tầng 3 (LaMa): để sau, M9 — không nạp ở M0.
"""
from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


def _region_bg_color(img: np.ndarray, region) -> tuple[int, int, int]:
    """Màu nền = median của viền ngoài bbox (không nằm trong vùng chữ)."""
    x1, y1, x2, y2 = region.bbox
    h, w = img.shape[:2]
    t = max(3, (y2 - y1) // 16)
    ring = []
    ring.append(img[max(0, y1 - t):min(h, y1), max(0, x1):min(w, x2)])
    ring.append(img[max(0, y2):min(h, y2 + t), max(0, x1):min(w, x2)])
    ring.append(img[max(0, y1):min(h, y2), max(0, x1 - t):min(w, x1)])
    ring.append(img[max(0, y1):min(h, y2), max(0, x2):min(w, x2 + t)])
    px = [p for p in ring if p.size > 0]
    if not px:
        return (255, 255, 255)
    allpx = np.concatenate([p.reshape(-1, img.shape[2]) for p in px])
    med = np.median(allpx, axis=0).astype(np.uint8)
    return tuple(int(v) for v in med)


def _bg_is_flat(img, region) -> bool:
    """Độ lệch chuẩn màu ở vùng viền: thấp -> nền phẳng -> tầng 1 đủ."""
    x1, y1, x2, y2 = region.bbox
    h, w = img.shape[:2]
    t = max(3, (y2 - y1) // 16)
    pad = img[max(0, y1 - t):min(h, y2 + t), max(0, x1 - t):min(w, x2 + t)]
    if pad.size == 0:
        return True
    return float(np.std(pad)) < 18.0


def inpaint_region(img: np.ndarray, region, max_tier: int = 2):
    """Trả về patch ảnh đã xoá chữ (crop quanh bbox)."""
    x1, y1, x2, y2 = region.bbox
    crop = img[y1:y2, x1:x2].copy()
    if crop.size == 0:
        return img[y1:y2, x1:x2]

    if region.mask is not None and cv2 is not None:
        mask = region.mask.astype(np.uint8)
        if mask.shape[:2] != crop.shape[:2]:
            mask = cv2.resize(mask, (crop.shape[1], crop.shape[0]),
                              interpolation=cv2.INTER_NEAREST)
        mask = (mask > 127).astype(np.uint8)
    else:
        # Không có mask từ detector ( RapidOCR DBNet chỉ cho polygon): dựng
        # mask gần đúng từ pixel tối trong crop (Otsu) — hợp bong bóng sáng;
        # nền tối/SFX sẽ lệch, chấp nhận ở v1 (doc 05: "che bằng ô trắng").
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        _, m = cv2.threshold(gray.astype(np.uint8), 0, 255,
                             cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        mask = m

    # Tầng 1: fill phẳng
    bg = _region_bg_color(img, region)
    if _bg_is_flat(img, region) or mask is None:
        if mask is not None:
            m = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        else:  # không có mask: fill nguyên vùng (kém — chỉ chống cháy)
            m = np.ones(crop.shape[:2], np.uint8) * 255
        crop[m > 0] = bg
        return crop

    # Tầng 2: cv2.inpaint Telea trên crop (chỉ patch, không cả trang)
    dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    if max_tier >= 2:
        return cv2.inpaint(crop, dil, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    crop[dil > 0] = bg
    return crop
