#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test M1: pipeline + API /pages/process + cache SQLite (doc 08 M1).

Không cần server chạy: dùng TestClient gọi app trực tiếp.

Cách chạy (Windows, dùng venv của backend — bắt buộc, deps nằm trong đó):
    backend\\.venv\\Scripts\\python.exe scripts\\smoke_m1.py

Nếu thiếu python-multipart (cần cho multipart form — thêm 2026-11-08):
    backend\\.venv\\Scripts\\python.exe -m pip install python-multipart
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
    import multipart  # noqa: F401  (python-multipart — cần cho POST multipart)
    from fastapi.testclient import TestClient
except ModuleNotFoundError as exc:
    print(f"[LỖI DEPS] Thiếu {exc.name} — chạy:\n"
          f"  backend\\.venv\\Scripts\\python.exe -m pip install python-multipart\n"
          f"hoặc chạy lại setup-backend.bat")
    sys.exit(1)


def make_page() -> np.ndarray:
    """Trang manga tổng hợp: 3 bong bóng, chữ EN, 1 vùng screentone."""
    img = np.full((1200, 800, 3), (255, 255, 255), np.uint8)
    for y in range(1000, 1200):  # nền nửa dưới có texture
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


def main() -> None:
    from app.api.app import app

    ok, buf = cv2.imencode(".png", make_page())
    payload = buf.tobytes()

    with TestClient(app) as c:
        h = c.get("/health").json()
        print("HEALTH:", json.dumps(h, ensure_ascii=False))
        assert h["status"] == "ok" and h["version"] >= "m1"

        t0 = time.perf_counter()
        r1 = c.post("/pages/process",
                    files={"image": ("page.png", payload, "image/png")},
                    data={"lang_src": "en"})
        t_ms = (time.perf_counter() - t0) * 1000
        j1 = r1.json()
        assert r1.status_code == 200, (r1.status_code, r1.text[:400])
        n_png = sum(1 for p in j1["patches"] if base64.b64decode(p["png_b64"] or b"x").startswith(b"\x89PNG"))
        print(f"\n[1st POST] {t_ms:.0f} ms | page_id={j1['page_id'][:12]} size={j1['size']} "
              f"regions={len(j1['regions'])} patchesPNGOK={n_png}/{len(j1['patches'])}")
        print("  timing_ms:", j1["timing_ms"])
        for reg in j1["regions"]:
            print(f"   [{reg['order']}] {reg['src_text']!r} bbox={reg['bbox']} "
                  f"kind={reg['kind']} conf={reg['score']:.3f} bg={reg['bg_color']}")

        assert len(j1["regions"]) >= 3, "OCR phải bắt được >=3 dòng chữ"
        ok_texts = " ".join(r["src_text"] for r in j1["regions"]).upper()
        for piece in ("WON", "HURT", "STAY", "CRY"):
            assert piece in ok_texts, f"OCR thiếu từ {piece!r} — got {ok_texts!r}"
        assert all(p["png_b64"] for p in j1["patches"]), "patch phải có b64 PNG"
        assert j1["regions"][0]["vi_text"] == "", "M1: vi_text rỗng (dịch là M2)"

        t0 = time.perf_counter()
        r2 = c.post("/pages/process",
                    files={"image": ("page.png", payload, "image/png")},
                    data={"lang_src": "en"})
        t_cache = (time.perf_counter() - t0) * 1000
        j2 = r2.json()
        same = (j2.get("cached") is True and j2["regions"] == j1["regions"]
                and all(j2["patches"][i]["png_b64"] == j1["patches"][i]["png_b64"]
                        for i in range(len(j1["patches"]))))
        print(f"\n[cache hit] {t_cache:.0f} ms | giống hết lần 1: {same}")
        assert same, "cache hit phải trả identical"

        rc1 = c.post("/chapters", json={"series": "smoke", "chapter": "01"}).json()
        rc2 = c.post("/chapters", json={"series": "smoke", "chapter": "01"}).json()
        assert rc1["chapter_id"] == rc2["chapter_id"], "get_or_create_chapter phải idempotent"
        print(f"[chapters] chapter_id={rc1['chapter_id']} (2 lần gọi = 1 id) OK")

        r3 = c.post("/pages/process", files={"image": ("x.png", b"junk", "image/png")})
        assert r3.status_code == 400, r3.status_code
        print("[ảnh hỏng] 400 OK")

        print("\n=== SMOKE M1: PASS ===")


if __name__ == "__main__":
    main()
