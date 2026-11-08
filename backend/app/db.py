"""SQLite (doc 02 §4): cache kết quả trang + chương.

Nguyên tắc (doc 07 §3b): cache theo `sha256 + lang + pipeline_ver` để đổi
model/thuật toán là tự vô hiệu cache. Ảnh patch lưu ra đĩa (cache/), DB chỉ
giữ đường dẫn → giữ DB nhỏ.

Mỗi lần gọi mở connection riêng: pipeline chỉ 1 worker (doc 07 §2), không
có contention; sqlite3 connection không dùng chung giữa các thread được nên
cách này an toàn nhất.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    hash         TEXT NOT NULL,
    lang         TEXT NOT NULL,
    pipeline_ver TEXT NOT NULL,
    result_json  TEXT NOT NULL,
    patches_dir  TEXT NOT NULL,
    created_at   REAL NOT NULL,
    PRIMARY KEY (hash, lang, pipeline_ver)
);
CREATE TABLE IF NOT EXISTS chapters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    series     TEXT NOT NULL,
    chapter    TEXT,
    url        TEXT,
    created_at REAL NOT NULL
);
"""


def _db_path() -> Path:
    p = get_settings().data_dir / "db.sqlite3"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect():
    conn = sqlite3.connect(_db_path(), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


# ---------- pages cache ----------

def get_page(image_hash: str, lang: str, pipeline_ver: str) -> dict[str, Any] | None:
    """Lấy kết quả cache. `patches_dir` trả về để tầng API nạp file patch."""
    with connect() as conn:
        row = conn.execute(
            "SELECT result_json, patches_dir FROM pages "
            "WHERE hash=? AND lang=? AND pipeline_ver=?",
            (image_hash, lang, pipeline_ver),
        ).fetchone()
    if row is None:
        return None
    return {"result": json.loads(row["result_json"]), "patches_dir": row["patches_dir"]}


def put_page(image_hash: str, lang: str, pipeline_ver: str,
             result: dict[str, Any], patches_dir: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pages "
            "(hash, lang, pipeline_ver, result_json, patches_dir, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (image_hash, lang, pipeline_ver, json.dumps(result), patches_dir, time.time()),
        )


# ---------- chapters ----------

def get_or_create_chapter(series: str, chapter: str | None = None,
                          url: str | None = None) -> int:
    """Trả về chapter_id của (series, chapter); chưa có thì tạo mới."""
    with connect() as conn:
        if chapter is not None:
            row = conn.execute(
                "SELECT id FROM chapters WHERE series=? AND chapter=?",
                (series, chapter),
            ).fetchone()
            if row is not None:
                return int(row["id"])
        now = time.time()
        cur = conn.execute(
            "INSERT INTO chapters (series, chapter, url, created_at) VALUES (?, ?, ?, ?)",
            (series, chapter, url, now),
        )
        return int(cur.lastrowid)
