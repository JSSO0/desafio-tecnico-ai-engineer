from fastapi import APIRouter, Response, status

from app.core.config import get_settings

router = APIRouter(tags=["ops"])


@router.get("/healthz", summary="Liveness probe")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
def readyz(response: Response) -> dict[str, object]:
    settings = get_settings()
    storage_ready = settings.database_path.parent.is_dir()
    if not storage_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if storage_ready else "not_ready",
        "checks": {
            "storage": storage_ready,
            "llm_configured": settings.provider_api_key is not None,
        },
        "provider": settings.llm_provider,
        "model": settings.llm_model,
    }
