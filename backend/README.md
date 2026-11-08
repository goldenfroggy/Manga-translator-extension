# Backend (Python 3.11, FastAPI)

Chạy được ngay ở M0: `/health` + pipeline detect → OCR → inpaint (dùng cho `scripts/benchmark.py`).

## Cài đặt & chạy (Windows)

```bat
setup-backend.bat          :: tạo .venv + cài deps
start-backend.bat          :: python -m app -> http://127.0.0.1:8791/health
```

## Benchmark M0 (bắt buộc trước khi chốt engine — doc 08 §1 M0)

```bat
python scripts\download_models.py              :: 1 lần, ticket ~80 MB vào backend\models\
.venv2\Scripts\python ..\scripts\benchmark.py  :: nếu chưa venv: python scripts\benchmark.py
```

Bỏ 10–20 trang manga (jpg/png/webp) vào `testset/en/` trước. Kết quả JSON: `benchmark/results-en.json`.

Ngưỡng mục tiêu (doc 07 §5): trang EN ≤ 4–6 s (không LLM), RAM đỉnh ≤ 1.5–2 GB, startup < 10 s.

## API (hiện tại)

- `GET /health` — trạng thái, model đã nạp, RAM

## Cấu trúc

- `app/pipeline/` — detector (ONNX/classic), ocr (RapidOCR), inpaint (tầng 1–2)
- `app/models/registry.py` — lazy load + unload LRU (doc 07 §3)
- `models/` — file ONNX (gitignored), tải bằng `scripts/download_models.py`
