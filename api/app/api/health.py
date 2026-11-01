import logging
import sqlite3
from contextlib import closing

from fastapi import APIRouter, Response, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ops"])


@router.get("/healthz", summary="Liveness probe")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
def readyz(response: Response) -> dict[str, object]:
    settings = get_settings()
    storage_ready = settings.database_path.parent.is_dir()
    database_ready = False

    if settings.database_path.exists():
        try:
            uri = f"file:{settings.database_path.as_posix()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as conn:
                total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            database_ready = total > 0
        except sqlite3.Error:
            logger.warning("readyz: banco inacessivel em %s", settings.database_path)
            database_ready = False

    ready = storage_ready and database_ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "storage": storage_ready,
            "database": database_ready,
            "llm_configured": settings.provider_api_key is not None,
        },
        "provider": settings.llm_provider,
        "model": settings.llm_model,
    }
