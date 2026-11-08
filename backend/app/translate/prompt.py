# -*- coding: utf-8 -*-
"""Khung prompt dịch theo trang (doc 04 §2).

M2: chỉ cần dịch THEO TRANG — 1 request chứa mọi bong bóng của trang, trả về
JSON cùng số mục. Glossary/xưng hô/tóm tắt chương là M5 (placeholder ở đây).
Thành ngữ: đọc `data/idioms_vi.json` → gợi ý bản Việt tương đương vào prompt.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# Đổi nghĩa khi prompt đổi → trans_ver đổi → tự vô hiệu cache dịch (doc 04 §7)
PROMPT_VER = "m2-p1"

_SRC_NAME = {"en": "Anh", "ja": "Nhật"}

_SYSTEM = """Bạn là dịch giả truyện tranh (manga) → tiếng Việt.
- Dịch TỰ NHIÊN như lời thoại, NGẮN GỌN để vừa bong bóng (tiếng Việt dài hơn tiếng Anh ~10–30%, ưu tiên cách nói ngắn).
- Có thể có lỗi OCR (ký tự sai/dư): sửa lỗi hiển nhiên theo ngữ cảnh, đừng bịa thêm nội dung.
- Giữ giọng điệu từng nhân vật.
- Thành ngữ / slang / chơi chữ: dịch theo NGHĨA, ưu tiên thành ngữ Việt tương đương; không dịch từng chữ.
- SFX (từ tượng thanh, chữ hiệu ứng) không nằm trong thoại thường — vẫn dịch nếu được đánh id.
- Mỗi dòng đầu vào đúng một bản dịch đầu ra: đủ số dòng, đúng id, không thêm/bỏ.
- TRẢ VỀ CHỈ JSON, schema: {"items":[{"id":<số nguyên>, "vi":"<bản dịch>"}]} — không kèm giải thích."""

_RETRY = ("Phản hồi trước KHÔNG đúng schema hoặc thiếu dòng. Trả về CHỈ JSON hợp lệ "
          "với ĐỦ {n} mục theo đúng id đã cho, không kèm chữ nào khác.")

_IDIOM_FLAGS = re.IGNORECASE


def load_idioms(data_dir: Path) -> list[dict]:
    """`data/idioms_vi.json` → list {pattern, vi, type}. File thiếu/hư → rỗng, không chết."""
    f = data_dir / "idioms_vi.json"
    if not f.exists():
        return []
    try:
        items = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(items, list):
        return []
    return [e for e in items if isinstance(e, dict) and e.get("pattern") and e.get("vi")]


def idioms_version(data_dir: Path) -> str:
    f = data_dir / "idioms_vi.json"
    if not f.exists():
        return "idiom0"
    try:
        return "idiom" + hashlib.md5(f.read_bytes()).hexdigest()[:8]
    except OSError:
        return "idiom0"


def idioms_hints(srcs: list[dict], idioms: list[dict]) -> str:
    """Khớp câu hỏi thành ngữ (doc 04 §4 lớp 1) → khối [GỢI_Ý_THÀNH_NGỮ]."""
    if not idioms:
        return ""
    page_text = " \n ".join(s["src"] for s in srcs).lower()
    hints = []
    for e in idioms:
        try:
            if re.search(e["pattern"], page_text, flags=_IDIOM_FLAGS):
                hints.append(f'"{e["pattern"]}" = {e["vi"]}')
        except re.error:
            if e["pattern"].lower() in page_text:
                hints.append(f'"{e["pattern"]}" = {e["vi"]}')
    if not hints:
        return ""
    return "[GỢI_Ý_THÀNH_NGỮ]\n" + "\n".join(hints)


def build_user_prompt(srcs: list[dict], lang: str, idioms: list[dict]) -> str:
    """User prompt: thu các vùng chữ (theo thứ tự đọc) + gợi ý thành ngữ."""
    parts = []
    hint = idioms_hints(srcs, idioms)
    if hint:
        parts.append(hint)
    lines = [f'{r["id"]}: "{r["src"]}"' for r in srcs]
    parts.append("[TRANG_HIỆN_TẠI]\n" + "\n".join(lines))
    return "\n\n".join(parts)


def build_messages(srcs: list[dict], lang: str, idioms: list[dict], retry: bool = False) -> list[dict]:
    if lang not in _SRC_NAME:  # M2 mới hỗ trợ en (ja là M7)
        lang = "en"
    system = _SYSTEM
    user = build_user_prompt(srcs, lang, idioms)
    if retry:
        system += "\n" + _RETRY.format(n=len(srcs))
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]
