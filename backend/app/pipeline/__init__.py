# Cấu trúc gói pipeline
from app.pipeline.detector import ClassicDetector, OnnxTextDetector, RapidOCRDetector
from app.pipeline.ocr import RapidOCREngine
from app.pipeline.types import Region, PageResult

__all__ = ["ClassicDetector", "OnnxTextDetector", "RapidOCRDetector", "RapidOCREngine", "Region", "PageResult"]
