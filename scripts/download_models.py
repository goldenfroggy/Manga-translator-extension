#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tải model cho backend vào backend/models/ (doc 02 §5, gitignored).

Nguồn đã kiểm tra:
- comic-text-detector.onnx: HuggingFace `mayocream/comic-text-detector-onnx`
  (chuyển ONNX từ dmMaze/comic-text-detector — GPL: chỉ dùng làm tham khảo,
  đừng copy code gốc vào repo theo doc 00).
- RapidOCR: bundle sẵn model PP-OCR trong pip package, không cần tải.

Cách chạy:
  python scripts/download_models.py                       # mặc định: detector
  python scripts/download_models.py --https-proxy http://... # nếu cần proxy
"""
import argparse
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS = ROOT / "backend" / "models"

URL = "https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def download(url: str, dest: pathlib.Path) -> None:
    existing = f" (đã có {dest.stat().st_size / 1e6:.1f} MB)" if dest.exists() else ""
    print(f"Tải {url}")
    print(f"  -> {dest}{existing}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as fh:
        prev = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            if fh.tell() - prev > 5 << 20:
                print(f"  ... {fh.tell() / 1e6:.0f} MB", flush=True)
                prev = fh.tell()
    tmp.replace(dest)
    print(f"  Xong: {dest.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Tải lại kể cả đã có")
    ap.add_argument("--https-proxy", default=None,
                    help="vd: http://127.0.0.1:7890 — nếu cần để ra mạng")
    args = ap.parse_args()

    MODELS.mkdir(parents=True, exist_ok=True)
    dest = MODELS / "comic-text-detector.onnx"

    if args.https_proxy:
        import os
        os.environ["HTTPS_PROXY"] = args.https_proxy

    if dest.exists() and not args.force:
        print(f"Đã có: {dest} — dùng --force để tải lại.")
    else:
        download(URL, dest)

    print("\nXong. Chạy benchmark: python scripts/benchmark.py --limit 10")


if __name__ == "__main__":
    main()
