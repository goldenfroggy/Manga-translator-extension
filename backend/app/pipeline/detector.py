"""Phát hiện vùng chữ (doc 03 §2-§3).

Hai engine:
- RapidOCRDetector: DBNet của RapidOCR chạy full page (MẶC ĐỊNH — nhanh, recall cao).
- OnnxTextDetector: comic-text-detector ONNX (chất lượng cao, có mask chữ cho
  inpaint — nhưng ~95MB và chậm ~12s/trang trên i3; dùng khi người dùng chọn
  chế độ "Chất lượng cao").
- ClassicDetector: ngưỡng + connected components, không cần model (fallback).
"""
from __future__ import annotations

import os

import numpy as np

from app.pipeline.types import Region

try:
    import cv2
except ImportError:
    cv2 = None

MAX_DETECT_EDGE = 1024  # doc 03: thu về cạnh dài <= 1024px cho detection


def _scale_image(img: np.ndarray, max_edge: int = MAX_DETECT_EDGE) -> tuple[np.ndarray, float, float, int, int]:
    h, w = img.shape[:2]
    scale = 1.0
    long_edge = max(h, w)
    if long_edge > max_edge:
        scale = max_edge / long_edge
    sw, sh = int(round(w * scale)), int(round(h * scale))
    small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA) if scale < 1.0 else img
    return small, scale, scale, h, w


class BaseDetector:
    name = "base"

    def __init__(self, max_edge: int = MAX_DETECT_EDGE):
        self.max_edge = max_edge

    def detect(self, img: np.ndarray) -> list[Region]:
        raise NotImplementedError


class OnnxTextDetector(BaseDetector):
    """comic-text-detector ONNX.

    Model xuất mask xác suất chữ; dùng threshold -> connected components để ra
    box chung với mask crop cho inpaint (doc 05 §2).
    """

    name = "onnx"

    def __init__(self, model_path, threads: int = 0, max_edge: int = MAX_DETECT_EDGE):
        import onnxruntime as ort

        super().__init__(max_edge)
        n = threads or max(1, (os.cpu_count() or 2) - 1)
        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
            sess_options=_sess_opts(n),
        )
        input_info = self.session.get_inputs()[0]
        self.input_name = input_info.name
        self.dynamic = input_info.shape[2] in (None, "H", "?", -1)  # chấp nhận H,W động

    def detect(self, img: np.ndarray) -> list[Region]:
        small, sx, sy, oh, ow = _scale_image(img, self.max_edge)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = np.transpose(rgb, (2, 0, 1))[None]
        if not self.dynamic:  # model fixed 1024x1024
            x = np.asarray([np.transpose(
                cv2.resize(small, (1024, 1024)).astype(np.float32)[:, :, ::-1] / 255.0,
                (2, 0, 1))])
        mask = self.session.run(None, {self.input_name: x})
        # đầu ra cuối cùng là mask xác suất [1,1,H,W]
        prob = np.asarray(mask[-1])[0, 0]
        prob = cv2.resize(prob, (small.shape[1], small.shape[0]),
                          interpolation=cv2.INTER_LINEAR)
        return _mask_to_regions(prob, sx, sy, oh, ow, kind="speech")


def _sess_opts(threads: int):
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    return opts


class RapidOCRDetector(BaseDetector):
    """Detector dùng DBNet của RapidOCR chạy full page (mặc định M0/M1).

    Vì sao: comic-text-detector ONNX nặng (~95MB, forward 1024×1024 chậm
    ~12s/trang trên i3); DBNet nhỏ (vài MB) chạy _tự_ full page
    0.5–0.8s/trang, recall cao. Nhược: không có mask chữ + không phân loại
    bubble/caption — inpaint sẽ dựng mask từ pixel (xem inpaint.py).
    Returned regions: bbox từ polygon min/max; polygon giữ nguyên để render.
    """

    name = "rapidocr"

    def __init__(self, threads: int = 0, max_edge: int = MAX_DETECT_EDGE):
        from rapidocr import RapidOCR

        super().__init__(max_edge)
        # Instance RIÊNG chỉ cho detection — RapidOCR corrupt state khi trộn
        # use_det/use_rec trên cùng instance (đã kiểm chứng bằng experiment)
        self.engine = RapidOCR()

    def detect(self, img: np.ndarray) -> list[Region]:
        H, W = img.shape[:2]
        out = self.engine(img, use_cls=False, use_rec=False)
        boxes = np.asarray(out.boxes if out.boxes is not None else [])
        regions: list[Region] = []
        for poly in boxes:
            xs, ys = poly[:, 0], poly[:, 1]
            regions.append(Region(
                bbox=(int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
                polygon=poly.tolist(),
                kind="speech",  # v1 không phân loại; LLM + UI tự sửa sau (doc 03)
            ))
        return _filter_regions(regions, (H, W))


class ClassicDetector(BaseDetector):
    """Fallback không model: ngưỡng tối -> dilate -> connected components."""

    name = "classic"

    def detect(self, img: np.ndarray) -> list[Region]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        small, sx, sy, oh, ow = _scale_image(gray, self.max_edge)
        # chữ trên bong bóng sáng: ngưỡng để lấy pixel tối
        _, binimg = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        binimg = cv2.dilate(binimg, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)))
        n, _, stats, _ = cv2.connectedComponentsWithStats(binimg, connectivity=8)
        regions: list[Region] = []
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if area < 80 or w < 20 or h < 12:
                continue
            regions.append(Region(
                bbox=(int(x / sx), int(y / sy), int((x + w) / sx) + 1, int((y + h) / sy) + 1),
                kind="speech",
            ))
        return _filter_regions(regions, img.shape)


def _mask_to_regions(prob, sx, sy, oh, ow, mask_thresh=0.5, kind="speech"):
    binmask = (prob > mask_thresh).astype(np.uint8) * 255
    binmask = cv2.dilate(binmask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(binmask, connectivity=8)
    regions: list[Region] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 100 or w < 16 or h < 10:
            continue
        crop = prob[y:y + h, x:x + w]
        regions.append(Region(
            bbox=(int(x / sx), int(y / sy), int((x + w) / sx) + 1, int((y + h) / sy) + 1),
            # mask crop ở độ phân giải detect; inpaint sẽ scale về ảnh gốc
            mask=np.asarray(crop, dtype=np.uint8),
            kind=kind,
        ))
    return _filter_regions(regions, (oh, ow))


def _filter_regions(regions: list[Region], shape) -> list[Region]:
    """Lọc box quá lớn (che gần hết trang, khả năng nhiễu)."""
    if not shape or len(shape) < 2:
        return regions
    area_page = shape[0] * shape[1]
    kept = []
    for r in regions:
        x1, y1, x2, y2 = r.bbox
        w, h = x2 - x1, y2 - y1
        if w * h > 0.45 * area_page:  # box chiếm gần nửa trang -> bỏ
            continue
        kept.append(r)
    return kept
