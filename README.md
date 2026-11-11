# Manga Translator Extension — Dịch manga EN/JA → VI
Extension Chrome + backend Python chạy local (OCR/inpaint không rời máy, chỉ text gửi LLM).

## Chạy backend (KHÔNG cần cài Python)

1. Copy cả repo sang máy (kèm `testset/en/` nếu muốn benchmark).
2. Chạy `setup-backend.bat` — tự tải Python 3.11 local (~11MB) về `backend\runtime\` và cài deps (~100MB, cần mạng).
3. Chạy `start-backend.bat` — server tại `http://127.0.0.1:8791/health`.
4. Tải model: `backend\runtime\python.exe scripts\download_models.py` (~95MB, chỉ cần cho mode "chất lượng cao").
5. Benchmark: `run-benchmark.bat --testset testset\en --limit 20`.
