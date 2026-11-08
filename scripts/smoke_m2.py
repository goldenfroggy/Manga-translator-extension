#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test M2: tầng dịch LLM qua /pages/process + cache dịch (doc 08 M2).

Dùng TestClient (không cần server). LLM endpoint đọc từ backend/.env —
phiên test dùng endpoint OpenAI-compatible local (không tốn quota).
Chạy:  backend\\.venv\\Scripts\\python.exe scripts\\smoke_m2.py
"""
import base64
import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import cv2
    import multipart  # noqa: F401
    from fastapi.testclient import TestClient
except ModuleNotFoundError as exc:
    print(f"[LỖI DEPS] Thiếu {exc.name} — chạy lại setup-backend.bat")
    sys.exit(1)


def make_page() -> np.ndarray:
    """Trang tổng hợp giống smoke_m1 — 3 bong bóng chữ EN (dùng chung ảnh để
    tận dụng cache-trang đã có, chỗ này chỉ đo tầng DỊCH)."""
    img = np.full((1200, 800, 3), (255, 255, 255), np.uint8)
    for y in range(1000, 1200):
        img[y, ::4] = (210, 210, 210)
    cv2.ellipse(img, (560, 160), (190, 110), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(img, (560, 160), (190, 110), 0, 0, 360, 0, 2)
    cv2.putText(img, "I WON'T LET", (430, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 0, 2)
    cv2.putText(img, "YOU HURT HER!", (430, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 0, 2)
    cv2.ellipse(img, (250, 520), (180, 100), 0, 0, 360, (240, 240, 240), -1)
    cv2.putText(img, "STAY BACK!", (130, 530), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
    cv2.ellipse(img, (520, 800), (170, 90), 0, 0, 360, (255, 255, 255), -1)
    cv2.putText(img, "Is she crying?", (400, 810), cv2.FONT_HERSHEY_SIMPLEX, 0.95, 0, 2)
    return img


def _post(client, payload):
    return client.post("/pages/process",
                       files={"image": ("page.png", payload, "image/png")},
                       data={"lang_src": "en"})


def main() -> None:
    from app.api.app import app
    from app.config import Settings
    from app.translate.translator import PageTranslator, _extract_json

    ok, buf = cv2.imencode(".png", make_page())
    payload = buf.tobytes()

    with TestClient(app) as c:
        h = c.get("/health").json()
        llm_ready = h["llm"]["configured"]
        print("HEALTH:", json.dumps(h, ensure_ascii=False))
        assert h["status"] == "ok" and h["version"] == "m2"
        if not llm_ready:
            print("⚠ LLM chưa cấu hình (backend/.env) — chỉ test ổn định-không-chết")

        t0 = time.perf_counter()
        r1 = _post(c, payload)
        j1 = r1.json()
        assert r1.status_code == 200, (r1.status_code, r1.text[:400])
        t1 = (time.perf_counter() - t0) * 1000
        srcs = [r for r in j1["regions"] if r["src_text"]]
        vis = [r for r in srcs if r["vi_text"]]
        print(f"\n[POST 1] {t1:.0f} ms | regions có chữ={len(srcs)} vi_text={len(vis)} "
              f"engine={j1['engine']['translate']} t_translate={j1['timing_ms']['translate']} ms")

        assert len(srcs) >= 3
        for r in srcs:
            print(f"   [{r['id']}] {r['src_text']!r} → {r['vi_text']!r}")
        if llm_ready:
            assert len(vis) == len(srcs), "LLM đã cấu hình mà còn region không có vi_text"
            print("   → đủ vi_text OK")
        else:
            assert j1["engine"]["translate"] in ("off", "failed", "none")

        # ---- cache-trang + cache-dịch: lần 2 phải nhanh và GIỐNG hệt ----
        t0 = time.perf_counter()
        r2 = _post(c, payload)
        j2 = r2.json()
        t2 = (time.perf_counter() - t0) * 1000
        same = (j2["regions"] == j1["regions"]
                and all(j2["patches"][i]["png_b64"] == j1["patches"][i]["png_b64"]
                        for i in range(len(j1["patches"]))))
        print(f"\n[POST 2 = cache] {t2:.0f} ms | t_translate={j2['timing_ms']['translate']} ms | "
              f"engine={j2['engine']['translate']} | identical j1: {same}")
        assert j2.get("cached") is True
        assert same, "lần 2 (cache) phải trả đúng như lần 1"
        if llm_ready:
            assert j2["engine"]["translate"] == "cache", "phải trùng cache dịch"
            assert j2["timing_ms"]["translate"] < 50, "cache dịch phải gần như 0 ms"

        # ---- trang KHÔNG có chữ: translate = none, không chết ----
        blank = np.full((300, 300, 3), 255, np.uint8)
        okb, bufb = cv2.imencode(".png", blank)
        rb = _post(c, bufb.tobytes())
        jb = rb.json()
        assert rb.status_code == 200 and len(jb["regions"]) == 0
        assert jb["engine"]["translate"] == "none", jb["engine"]
        print(f"\n[trang trống] 200, translate=none OK")

    # ---- LLM lỗi (URL rác) → vi_text rỗng + flag failed, KHÔNG exception ----
    bad = Settings(llm_base_url="http://127.0.0.1:9/none",
                   llm_api_key="k", llm_model="m", llm_timeout_s=3)
    tr = PageTranslator(bad)
    fake = {"regions": [{"id": 1, "src_text": "hello there"}],
            "timing_ms": {}, "engine": {}}
    tr.translate_result(fake, "en")
    assert not fake["regions"][0].get("vi_text") and fake["engine"]["translate"] == "failed", fake
    print("[LLM lỗi] vi_text rỗng + engine=failed OK (trang không chết)")

    # ---- LLM chưa cấu hình → off ----
    off = Settings(llm_api_key="", llm_base_url="", llm_model="")
    fake2 = {"regions": [{"id": 1, "src_text": "hi"}], "timing_ms": {}, "engine": {}}
    PageTranslator(off).translate_result(fake2, "en")
    assert fake2["engine"]["translate"] == "off"
    print("[chưa cấu hình] engine=off OK")

    # ---- parser: codefence / id dạng chuỗi / dư mục / thiếu mục ----
    txt = '```json\n{"items": [{"id": "1", "vi": "xin chào"}, {"id": 99, "vi": "dư"}]}\n```'
    items = PageTranslator._parse(txt, {"1", "2"})
    assert items == {"1": "xin chào"}, items  # id chuỗi OK, id lạ bị loại, id 2 thiếu → không có
    assert _extract_json("rác trước {\"a\":1} rác sau") == {"a": 1}
    print("[parser] codefence + id chuỗi + lọc id lạ OK")

    print("\n=== SMOKE M2: PASS ===")


if __name__ == "__main__":
    main()
