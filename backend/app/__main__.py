"""Entry: `python -m app` (khớp hướng dẫn trong UI extension, doc 06 §5)"""
import uvicorn

from app.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run("app.api.app:app", host=s.host, port=s.port, log_level="info")


if __name__ == "__main__":
    main()
