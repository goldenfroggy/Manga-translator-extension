#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Benchmark M0 trên máy thật 8GB/i3 (doc 08 §1, doc 07 §4).

Đo từng tầng trên các ảnh trong testset/{en,ja}/:
  detect -> ocr -> inpaint (tầng 1 + tầng 2)

Xuất: bảng thời gian + RAM đỉnh ra console (JSON ở benchmark/results-{lang}.json).
Chạy trước khi tải model: dùng ClassicDetector (không model) — số liệu chỉ mang
tính tương đối; với model thật hãy chạy scripts/download_models.py trước.

Cách chạy:
  python scripts/benchmark.py --testset testset/en --limit 20
  python scripts/benchmark.py --testset testset/ja --limit 5 --onnx backend/models/comic-text-detector.onnx
"""
import argparse
import json
import os
import pathlib
import platform
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# Windows console: đảm bảo in dấu tiếng Việt không lỗi cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def now_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def load_engines(detector_kind: str, onnx_path: pathlib.Path, threads: int, max_edge: int):
    """Nạp engine (đo thời gian load — quan trọng vì khởi động backend <10s)."""
    try:
        from app.pipeline.detector import ClassicDetector, OnnxTextDetector, RapidOCRDetector
        from app.pipeline.ocr import RapidOCREngine
    except ModuleNotFoundError as exc:
        sys.exit(
            f"Thiếu thư viện: {exc.name}. Bạn đang dùng Python không có deps của backend.\n"
            "Cách 1 (khuyến nghị, Windows): chạy setup-backend.bat, sau đó dùng "
            "run-benchmark.bat, hoặc:\n"
            "  backend\\.venv\\Scripts\\python.exe scripts\\benchmark.py --testset testset\\en\n"
            "Cách 2: cài deps thẳng vào Python hiện tại:\n"
            "  python -m pip install \"numpy>=2.0\" opencv-python-headless rapidocr onnxruntime psutil"
        )

    loads: dict[str, float] = {}
    if detector_kind == "rapidocr":
        t0 = time.perf_counter()
        det = RapidOCRDetector(max_edge=max_edge)
        loads["detector_load_ms"] = now_ms(t0)
        det_name = "rapidocr(DBNet full page)"
    elif detector_kind == "onnx":
        t0 = time.perf_counter()
        det = OnnxTextDetector(onnx_path, threads=threads, max_edge=max_edge)
        loads["detector_load_ms"] = now_ms(t0)
        det_name = "onnx(comic-text-detector)"
    else:
        det = ClassicDetector(max_edge=max_edge)
        loads["detector_load_ms"] = 0.0
        det_name = "classic(threshold+CC)"

    t0 = time.perf_counter()
    ocr = RapidOCREngine()
    loads["ocr_load_ms"] = now_ms(t0)
    ocr_name = "rapidocr(rec-only)"

    return det, det_name, ocr, ocr_name, loads


def measure_ram():
    import psutil

    return psutil.Process().memory_info().rss


def run_page(img_path: pathlib.Path, det, ocr, max_tier: int):
    import cv2

    from app.pipeline.inpaint import inpaint_region

    img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Không đọc được ảnh: {img_path}")

    peak = measure_ram()
    timing: dict[str, float] = {}

    t0 = time.perf_counter()
    regions = det.detect(img)
    timing["detect_ms"] = now_ms(t0)
    peak = max(peak, measure_ram())

    if regions:
        t0 = time.perf_counter()
        ocr.read_regions(img, regions)
        timing["ocr_ms"] = now_ms(t0)
        peak = max(peak, measure_ram())

        t0 = time.perf_counter()
        patches = [inpaint_region(img, r, max_tier=max_tier) for r in regions]
        timing["inpaint_ms"] = now_ms(t0)
        peak = max(peak, measure_ram())
    else:
        timing["ocr_ms"] = 0.0
        timing["inpaint_ms"] = 0.0

    texts = [r for r in regions if r.src_text]
    return {
        "file": img_path.name,
        "regions": len(regions),
        "ocr_ok": len(texts),
        "ocr_conf_med": (sorted(r.score for r in texts)[len(texts) // 2]
                         if texts else None),
        "timing_ms": {k: round(v, 1) for k, v in timing.items()},
        "peak_ram_mb": round(peak / 1e6, 1),
        "sample_texts": [r.src_text for r in texts[:3]],
    }


def fmt_table(rows: list[dict]) -> str:
    cols = ["file", "regions", "ocr_ok", "detect_ms", "ocr_ms",
            "inpaint_ms", "total_ms", "peak_ram_mb"]
    out = [" | ".join(f"{c:>12}" for c in cols)]
    out.append("-+-".join("-" * 12 for _ in cols))
    for r in rows:
        t = r["timing_ms"]
        total = t["detect_ms"] + t["ocr_ms"] + t["inpaint_ms"]
        out.append(" | ".join([
            f"{r['file'][:12]:>12}", f"{r['regions']:>12}", f"{r['ocr_ok']:>12}",
            f"{t['detect_ms']:>12.1f}", f"{t['ocr_ms']:>12.1f}",
            f"{t['inpaint_ms']:>12.1f}", f"{total:>12.1f}",
            f"{r['peak_ram_mb']:>12.1f}",
        ]))
    return "\n".join(out)


def summarize(rows: list[dict], loads: dict) -> str:
    if not rows:
        return "Không có ảnh nào trong testset — hãy chép 10–20 trang manga vào đây."
    avg = lambda key: sum(r["timing_ms"][key] for r in rows) / len(rows)  # noqa: E731
    total_avg = avg("detect_ms") + avg("ocr_ms") + avg("inpaint_ms")
    lines = [
        f"--- TÓM TẮT ({len(rows)} ảnh) ---",
        f"detect  TB: {avg('detect_ms'):8.1f} ms",
        f"ocr     TB: {avg('ocr_ms'):8.1f} ms",
        f"inpaint TB: {avg('inpaint_ms'):8.1f} ms",
        f"THAM CHIẾU trang (không tính LLM): {total_avg:8.1f} ms "
        f"(ngưỡng doc 07: ≤ 4000–6000 ms chế độ Nhanh)",
        f"RAM đỉnh  : {max(r['peak_ram_mb'] for r in rows):8.1f} MB "
        f"(ngưỡng backend ≤ 1500–2000 MB)",
        f"Load model: {loads} (khởi động backend < 10 s)",
        f"CPU máy   : {platform.processor() or platform.machine()}, "
        f"{os.cpu_count()} threads",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark pipeline M0")
    ap.add_argument("--testset", default=str(ROOT / "testset" / "en"))
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--max-tier", type=int, default=2, choices=[1, 2],
                    help="Tầng inpaint cao nhất (3=LaMa, để sau)")
    ap.add_argument("--detector", choices=["rapidocr", "onnx", "classic"],
                    default="rapidocr",
                    help="rapidocr = DBNet full page (mặc định, nhanh); "
                         "onnx = comic-text-detector (chậm, có mask chữ)")
    ap.add_argument("--model-dir", default=str(ROOT / "backend" / "models"))
    ap.add_argument("--threads", type=int, default=0,
                    help="0 = tự chọn (n_cpu - 1) theo doc 07")
    ap.add_argument("--max-edge", type=int, default=1024,
                    help="Cạnh dài tối đa cho detect (hạ nếu chậm: 768)")
    args = ap.parse_args()

    testset = pathlib.Path(args.testset)
    if not testset.is_dir():
        sys.exit(f"Không tìm thấy thư mục testset: {testset}")
    images = sorted(p for p in testset.iterdir()
                    if p.suffix.lower() in IMG_EXTS and not p.name.startswith("_"))[: args.limit]
    if not images:
        print(f"Bỏ ảnh manga (jpg/png/webp) vào {testset}/ rồi chạy lại.")
        return

    onnx_path = pathlib.Path(args.model_dir) / "comic-text-detector.onnx"
    warn = "" if onnx_path.exists() else (
        "  (!) Chưa có model ONNX — đang dùng ClassicDetector. "
        "Chạy: python scripts/download_models.py")
    print(f"Engine chuẩn bị...{warn}")
    det, det_name, ocr, ocr_name, loads = load_engines(
        args.detector, onnx_path, args.threads, args.max_edge)

    rows = []
    for p in images:
        try:
            rows.append(run_page(p, det, ocr, args.max_tier))
        except Exception as exc:  # noqa: BLE001 — đo được trang nào nên trang đó
            print(f"  Lỗi {p.name}: {exc}")

    print()
    print(fmt_table(rows))
    print()
    print(summarize(rows, loads))

    out = ROOT / "benchmark" / f"results-{testset.name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "testset": str(testset),
        "detector": det_name, "ocr": ocr_name,
        "max_tier": args.max_tier,
        "max_edge": args.max_edge,
        "loads_ms": loads,
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKết quả JSON: {out}")


if __name__ == "__main__":
    main()
