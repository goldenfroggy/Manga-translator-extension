# -*- coding: utf-8 -*-
"""Tầng dịch trang bằng LLM (M2, doc 04 §2 / §6).

Nguyên tắc:
- 1 request / trang: gửi mọi vùng có chữ (theo thứ tự đọc), nhận JSON map
  id → vi_text, đúng số mục. Retry 1 lần khi JSON dị dạng/thiếu, vẫn lỗi →
  vùng đó để `vi_text` rỗng + flag (trang KHÔNG chết — doc 02 §6).
- Chỉ gửi TEXT — ảnh không rời máy (ràng buộc riêng tư).
- Cache riêng cho tầng dịch theo `sha256(texts) + lang + trans_ver`
  (prompt_ver + model + idioms — doc 04 §7); cache-trang M1 giữ nguyên.

`translate_result()` làm việc trực tiếp trên dict JSON của đáp án (không phải
PageResult) để dùng lại được cả cho kết quả cache-trang lẫn kết quả mới.

Cài mặc định: 1 request/trang (đúng doc 04 §2 — rẻ, giữ ngữ cảnh). Trang dài
quá → endpoint nhiều upstream model từ chối (lỗi 2026-11-08: page 47 vùng →
400 "model unavailable" lặp lại) → FALLBACK = chia lô ≤ MAX_BATCH vùng, mỗi
lô 1 request; gom kết quả theo id.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

from app.config import Settings, get_settings
from app.db import get_translation, put_translation
from app.translate.provider import LLMError, OpenAICompatProvider
from app.translate.prompt import PROMPT_VER, build_messages, idioms_version, load_idioms

_MAX_BATCH = 20  # số vùng tối đa/request khi fallback chia lô

log = logging.getLogger("translate")


def _extract_json(text: str) -> dict | None:
    """Rút JSON object từ lời trả lời (chịu codefence ```json ...```)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except ValueError:
        pass
    i, j = text.find("{"), text.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(text[i:j + 1])
        except ValueError:
            return None
    return None


class PageTranslator:
    """Điền `vi_text` vào `regions` của 1 trang; 1 instance dùng cả server."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._provider = OpenAICompatProvider(self.settings)
        self._idioms = load_idioms(self.settings.data_dir)

    # ------ API chính -----------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return self._provider.configured

    def translate_result(self, result: dict, lang: str = "en") -> None:
        """Điền vi_text vào result["regions"] (in-place) + timing_ms/engine flags.

        Flags `result["engine"]["translate"]`:
          "none" (trang không có chữ) | "off" (chưa cấu hình .env)
          | "cache" (trùng bản dịch cũ) | "llm" (mới dịch) | "failed" (LLM lỗi).
        """
        t0 = time.perf_counter()
        result["timing_ms"]["translate"] = 0
        result["engine"]["translate"] = "off"

        regions = result.get("regions") or []
        todo = [r for r in regions if r.get("src_text")]
        if not todo:
            result["engine"]["translate"] = "none"
            return
        if not self.configured:
            return
        result["engine"]["translate"] = "failed"  # sẽ bị ghi đè khi thành công

        srcs = [{"id": r["id"], "src": r["src_text"]} for r in todo]
        trans_ver = f"{PROMPT_VER}+{self.settings.llm_model}+{idioms_version(self.settings.data_dir)}"
        key = self._src_hash(srcs, lang, trans_ver)

        cached = get_translation(key, lang, trans_ver)
        if cached is not None:
            self._fill(todo, cached)
            result["engine"]["translate"] = "cache"
        else:
            items = self._request_vi(srcs, lang)
            if items:
                self._fill(todo, items)
                put_translation(key, lang, trans_ver, items)
                result["engine"]["translate"] = "llm"

        result["timing_ms"]["translate"] = round((time.perf_counter() - t0) * 1000)

    # ------ nội bộ ---------------------------------------------------------------------

    @staticmethod
    def _src_hash(srcs: list[dict], lang: str, trans_ver: str) -> str:
        blob = json.dumps({"lang": lang, "ver": trans_ver, "src": srcs},
                          ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _request_vi(self, srcs: list[dict], lang: str) -> dict[str, str] | None:
        """Dịch toàn trang: full-page 1 request → thiếu/lỗi thì chia lô fallback.

        Trả map id→vi (thiếu vài id nếu cả full lẫn chia lô đều không dịch được)
        hoặc None khi không dịch được gì.
        """
        wanted = {str(r["id"]) for r in srcs}
        items = self._translate_batch(srcs, lang)
        if wanted.issubset(items):
            return items

        # Fallback chia lô (bẫy 2026-11-08: trang >~25 vùng bị endpoint từ chối)
        missing = [r for r in srcs if str(r["id"]) not in items]
        if len(missing) > _MAX_BATCH:
            log.warning("LLM full-page thiếu %d/%d vùng → chia lô %d",
                        len(missing), len(srcs), _MAX_BATCH)
            for i in range(0, len(missing), _MAX_BATCH):
                items.update(self._translate_batch(missing[i:i + _MAX_BATCH], lang))
        return items or None

    def _translate_batch(self, srcs: list[dict], lang: str) -> dict[str, str]:
        """1 lô = 1 request + retry nhắc-định-dạng 1 lần. LLM lỗi sẵn (mạng/quota
        429/5xx) → trả {} ngay, tầng `_request_vi` thử fallback chia lô."""
        wanted = {str(r["id"]) for r in srcs}
        items: dict[str, str] = {}
        for attempt in range(2):
            try:
                text = self._provider.chat(
                    build_messages(srcs, lang, self._idioms, retry=(attempt == 1)))
            except LLMError as exc:
                self._last_err = str(exc)[:200]
                log.warning("LLM lỗi (%d vùng): %s", len(srcs), self._last_err)
                time.sleep(1.5)  # backoff thô — 429/5xx trả về nhanh thì chờ tí
                break  # lỗi sẵn → bỏ nhịp retry, để fallback xử lý
            parsed = self._parse(text, wanted)
            items.update(parsed)
            if parsed and wanted.issubset(items):
                break  # đủ mọi id — khỏi retry
        return items

    @staticmethod
    def _parse(text: str, wanted: set[str]) -> dict[str, str]:
        """JSON → map id→vi; chỉ nhận đúng id đã hỏi, vi_text sạch khoảng trắng."""
        data = _extract_json(text)
        if not isinstance(data, dict):
            return {}
        raw = data.get("items") if isinstance(data.get("items"), list) else \
            data.get("translations") if isinstance(data.get("translations"), list) else \
            data.get("results") if isinstance(data.get("results"), list) else None
        out: dict[str, str] = {}
        for entry in raw or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("id", "")).strip()
            vi = entry.get("vi")
            if key in wanted and isinstance(vi, str) and vi.strip():
                out[key] = " ".join(vi.split())
        return out

    @staticmethod
    def _fill(todo: list[dict], items: dict[str, str]) -> None:
        for r in todo:
            vi = items.get(str(r["id"]))
            if vi:
                r["vi_text"] = vi
