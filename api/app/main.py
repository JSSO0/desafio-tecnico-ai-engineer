from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

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
