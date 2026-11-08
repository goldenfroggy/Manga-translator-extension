"""Quản lý model (doc 07 §3): lazy load + LRU unload sau khi nhàn rỗi.

M0 chỉ nạp detector lúc khởi động; các model nặng (OCR Nhật, LaMa, dịch local)
sẽ vào đây ở M1+.
"""
from __future__ import annotations

import time


class ModelRegistry:
    _shared: ModelRegistry | None = None

    def __init__(self, settings):
        self.settings = settings
        self._loaded: dict[str, tuple[object, float]] = {}  # name -> (obj, last_used)

    @classmethod
    def shared(cls, settings) -> "ModelRegistry":
        if cls._shared is None:
            cls._shared = ModelRegistry(settings)
        return cls._shared

    def touch(self, name: str, obj: object) -> object:
        self._loaded[name] = (obj, time.monotonic())
        return obj

    def evict_idle(self) -> list[str]:
        limit = self.settings.idle_unload_minutes * 60
        now = time.monotonic()
        evicted = [n for n, (_, used) in self._loaded.items() if now - used > limit]
        for n in evicted:
            del self._loaded[n]
        return evicted

    def list_loaded(self) -> list[str]:
        return sorted(self._loaded)

    @staticmethod
    def ram_usage_mb() -> float:
        import psutil

        return round(psutil.Process().memory_info().rss / 1e6, 1)
