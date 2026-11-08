# API v1 (doc 02 §3). M0/chỉ /health; M1 sẽ thêm /pages/process
from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.registry import ModelRegistry

router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)):
    reg = ModelRegistry.shared(settings)
    llm = settings
    return {
        "status": "ok",
        "models_loaded": reg.list_loaded(),
        "ram": reg.ram_usage_mb(),
        "version": "m2",
        "llm": {
            "configured": bool(llm.llm_api_key and llm.llm_base_url and llm.llm_model),
            "model": llm.llm_model,  # KHÔNG trả api key
        },
    }
