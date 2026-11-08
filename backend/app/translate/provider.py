"""Provider LLM qua HTTP OpenAI-compatible (doc 04 §2).

1 class dùng cho mọi nhà cung cấp: Gemini (endpoint `/v1beta/openai/` của
Google), DeepSeek, OpenRouter, OpenAI, hoặc endpoint local — tất cả đều dùng
`POST {base_url}/chat/completions`. Đổi provider = đổi .env, không đổi code.

Không dùng thư viện `openai` — chỉ httpx (nhẹ, ít token, đã có trong deps).
Key chỉ đọc từ Settings (nạp từ .env) — không log, không trả về trên API.
"""
from __future__ import annotations

import httpx

from app.config import Settings, get_settings


class LLMError(Exception):
    """Lỗi gọi LLM (mạng / 4xx 5xx / phản hồi dị dạng) — tầng trên quyết định fallback."""


class OpenAICompatProvider:
    """Chat completions OpenAI-compatible; trả `content` (str) hoặc raise LLMError."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        s = self.settings
        return bool(s.llm_base_url and s.llm_model and s.llm_api_key)

    def chat(self, messages: list[dict], temperature: float | None = None) -> str:
        s = self.settings
        if not self.configured:
            raise LLMError("LLM chưa cấu hình (thiếu MANGA_LLM_BASE_URL/MODEL/API_KEY)")

        url = s.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {s.llm_api_key}"}
        body = {
            "model": s.llm_model,
            "messages": messages,
            "stream": False,  # một số endpoint mặc định SSE — ép JSON một khối
            "response_format": {"type": "json_object"},  # yêu cầu đầu ra JSON
            "temperature": s.llm_temperature if temperature is None else temperature,
        }
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=s.llm_timeout_s)
        except httpx.HTTPError as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        if r.status_code != 200:
            # 429/5xx → tầng trên retry; còn lại là lỗi cấu hình/quyền
            raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")

        try:
            msg = r.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"Phản hồi dị dạng: {r.text[:300]}") from exc

        content = msg.get("content") or ""
        if not content.strip():
            raise LLMError("content rỗng (model không trả lời)")
        return content
