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
    vi_text: str = ""


@dataclass
class PageResult:
    regions: list[Region] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)
    engine: dict[str, str] = field(default_factory=dict)  # "detector": "onnx"|"classic", ...
