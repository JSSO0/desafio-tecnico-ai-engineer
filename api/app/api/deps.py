from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.agent.runner import AgentRunner
from app.core.config import Settings, get_settings
from app.core.errors import SessionError
from app.runtime.store import RuntimeStore, Session

_STORE: dict[str, RuntimeStore] = {}

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token opaco devolvido por POST /v1/sessions. Nao e JWT e nao carrega dados.",
)


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> RuntimeStore:
    key = str(settings.runtime_path)
    if key not in _STORE:
        _STORE[key] = RuntimeStore(settings.runtime_path)
    return _STORE[key]


def get_runner() -> AgentRunner:
    """Ponto de substituicao: os testes trocam o agente real por um roteirizado."""
    return AgentRunner()


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_session(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    store: Annotated[RuntimeStore, Depends(get_store)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> Session:
    """Authenticates by opaque session token. Invalid, revoked and expired tokens are all 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("missing_token", "Envie o cabecalho Authorization: Bearer <token>.")

    try:
        return store.by_token(credentials.credentials, settings.session_ttl_minutes)
    except SessionError as exc:
        raise _unauthorized(exc.code, exc.message) from exc


def assert_own_session(session: Session, session_id: str) -> None:
    """The token only reaches its own session: the id in the URL is not a credential."""
    if session.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": "Sessao nao encontrada."},
        )
