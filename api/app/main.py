import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.db.build import build_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.database_path.exists():
        logger.info(
            "base ausente em %s — construindo a partir de %s",
            settings.database_path,
            settings.data_dir,
        )
        report = build_database(settings.database_path, settings.data_dir, settings.policies_dir)
        logger.info("base construida: %s", json.dumps(report, ensure_ascii=False))
    yield


app = FastAPI(
    title="Empório da Música — Agente de Atendimento",
    version=settings.app_version,
    summary="Agente de atendimento ao cliente (desafio técnico AI Engineer — Artefact)",
    description=(
        "API do agente de atendimento da Empório da Música. "
        "Consome dados operacionais (catálogo, pedidos) por ferramentas determinísticas "
        "e políticas internas por recuperação por seção. "
        "Autenticação por token opaco de sessão (`Authorization: Bearer`)."
    ),
    lifespan=lifespan,
)
app.include_router(health_router)


@app.get("/v1/meta", tags=["ops"], summary="Configuração ativa do agente")
def meta() -> dict[str, object]:
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "llm_configured": settings.provider_api_key is not None,
        "app_version": settings.app_version,
    }
