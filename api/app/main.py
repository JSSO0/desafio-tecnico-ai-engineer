import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.prompts import active_prompt_version
from app.api.chat import router as chat_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.schemas import MetaResponse
from app.api.sessions import router as sessions_router
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
        "Todas as rotas de atendimento exigem `Authorization: Bearer <access_token>` obtido em "
        "`POST /v1/sessions`. A chave do provedor de LLM nunca sai do servidor."
    ),
    lifespan=lifespan,
)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(chat_router)

_origens = [origem.strip() for origem in settings.cors_origins.split(",") if origem.strip()]
if _origens:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origens,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        # sem isto o navegador nao consegue ler os cabecalhos de limite e orcamento
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Budget-Remaining",
        ],
    )


@app.get(
    "/v1/meta",
    response_model=MetaResponse,
    tags=["ops"],
    summary="Configuração ativa do agente",
)
def meta() -> MetaResponse:
    return MetaResponse(
        provider=settings.llm_provider,
        model=settings.llm_model,
        llm_configured=settings.provider_api_key is not None,
        prompt_version=active_prompt_version(),
        app_version=settings.app_version,
    )
