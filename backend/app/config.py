# Cấu hình backend. API keys chỉ nằm ở .env (doc 01 §2)
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MANGA_", env_file=".env", extra="ignore")

    # Server (doc 06 §6: bind chi 127.0.0.1)
    host: str = "127.0.0.1"
    port: int = 8791

    # Paths
    model_dir: Path = BACKEND_ROOT / "models"
    data_dir: Path = BACKEND_ROOT / "data"
    cache_dir: Path = BACKEND_ROOT / "cache"

    # Perf (doc 07 §2: chua 1 luong cho trinh duyet)
    intra_op_threads: int = 0  # 0 = auto (n_cpu - 1)

    # Model manager (doc 07 §3)
    idle_unload_minutes: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
