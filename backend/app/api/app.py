from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.pages import router as pages_router
from app.db import init_db
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # bảng pages/chapters — idempotent
    yield


app = FastAPI(title="Manga Translator backend", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(pages_router)
