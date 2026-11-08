# Kiểu dữ liệu chia sẻ giữa các tầng pipeline (doc 03 §5)
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# kind: speech (bong bóng thoại), caption, sfx, ocr_low (cờ conf thấp)
RegionKind = str


@dataclass
class Region:
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2 trong toạ độ ảnh gốc
    polygon: list | None = None  # polygon (dBNet) nếu có — dùng cho inpaint/render
    mask: np.ndarray | None = None  # mặt nạ chữ (crop), dùng cho inpaint
    kind: RegionKind = "speech"
    score: float = 0.0
    src_text: str = ""
    vi_text: str = ""  # M1: rỗng — dịch là M2
    order: int = 0  # thứ tự đọc (hàng trên→dưới, phải→trái) — orchestrate gán
    # Màu gợi ý cho render (doc 02 §3): M1 đo thô, render M4 dùng/sửa sau
    text_color: tuple[int, int, int] | None = None
    bg_color: tuple[int, int, int] | None = None


@dataclass
class PageResult:
    regions: list[Region] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)
    engine: dict[str, str] = field(default_factory=dict)  # "detector": "onnx"|"classic", ...
    # (bbox, patch_bgr) theo thứ tự regions — API layer encode PNG + b64
    patches: list[tuple[tuple[int, int, int, int], np.ndarray]] = field(default_factory=list)
