from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import assert_own_session, get_store, require_session
from app.api.schemas import MessageOut, MessagesResponse, SessionCreated, UsageResponse
from app.core.config import Settings, get_settings
from app.runtime.store import RuntimeStore, Session

router = APIRouter(prefix="/v1/sessions", tags=["sessoes"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionCreated,
    summary="Abre uma sessao de atendimento",
    description=(
        "Cria uma sessao anonima e devolve o `access_token` (opaco, 256 bits, 30 min deslizantes). "
        "Nenhuma credencial de provedor de LLM e exposta ao cliente: a chave fica no servidor. "
        "A criacao e limitada por origem, porque cada sessao carrega um orcamento de tokens."
    ),
    responses={
        429: {
            "description": "Muitas sessoes abertas pela mesma origem na ultima hora",
        }
    },
)
def create_session(
    request: Request,
    store: Annotated[RuntimeStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionCreated:
    origem = request.client.host if request.client else "desconhecida"

    if store.creations_by_ip(origem) >= settings.max_sessions_per_hour:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "too_many_sessions",
                "message": "Muitas sessoes abertas em pouco tempo. Tente de novo mais tarde.",
            },
            headers={"Retry-After": "3600"},
        )

    store.register_creation(origem)
    token, session = store.create(settings.session_ttl_minutes, settings.budget_tokens)
    return SessionCreated(
        access_token=token,
        expires_at=session.expires_at,
        budget_tokens=session.budget_tokens,
        session_id=session.session_id,
    )


@router.get(
    "/{session_id}/usage",
    response_model=UsageResponse,
    summary="Consumo de tokens da sessao",
    description="Tokens consumidos, numero de turnos e saldo do orcamento da sessao.",
)
def session_usage(
    session_id: str,
    session: Annotated[Session, Depends(require_session)],
    store: Annotated[RuntimeStore, Depends(get_store)],
) -> UsageResponse:
    assert_own_session(session, session_id)
    return UsageResponse(**store.usage(session))


@router.get(
    "/{session_id}/messages",
    response_model=MessagesResponse,
    summary="Historico da sessao",
)
def session_messages(
    session_id: str,
    session: Annotated[Session, Depends(require_session)],
    store: Annotated[RuntimeStore, Depends(get_store)],
) -> MessagesResponse:
    assert_own_session(session, session_id)
    return MessagesResponse(
        session_id=session.session_id,
        messages=[MessageOut(**item) for item in store.messages(session.session_id)],
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Encerra a sessao e apaga o historico",
    description=(
        "Revoga o token e remove as mensagens da sessao. Atende ao direito de exclusao descrito "
        "na politica de privacidade (secao 9)."
    ),
)
def revoke_session(
    session_id: str,
    session: Annotated[Session, Depends(require_session)],
    store: Annotated[RuntimeStore, Depends(get_store)],
) -> None:
    assert_own_session(session, session_id)
    store.revoke(session.session_id)
