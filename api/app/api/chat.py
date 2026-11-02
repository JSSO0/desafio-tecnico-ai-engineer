from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain.messages import AIMessage, HumanMessage

from app.agent.runner import AgentRunner, TurnAccumulator
from app.agent.session import SessionContext
from app.api.deps import get_runner, get_store, require_session
from app.api.schemas import ChatRequest, ErrorResponse
from app.audit.log import audit_event
from app.core.config import Settings, get_settings
from app.core.turn import TurnOutcome
from app.db.connection import connect
from app.guards.input import Verdict, screen
from app.runtime.store import RuntimeStore, Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["atendimento"])

SSE_DOC = """Resposta em `text/event-stream`. Cada evento tem `event:` e `data:` (JSON).

| evento | data | significado |
|---|---|---|
| `token` | `{delta}` | pedaco da resposta; concatene |
| `tool_call` | `{name, args, status}` | ferramenta iniciada (`start`) ou concluida (`end`) |
| `card` | `{tipo, dados}` | dado estruturado: `produto`, `pedido`, `politica`, `pagamento` |
| `guard` | `{tipo, acao, texto}` | guardrail atuou; se `acao=substituir_resposta`, troque o texto |
| `usage` | `{tokens_in, tokens_out, tokens_total, remaining, budget_tokens}` | consumo acumulado |
| `done` | `{message_id, latency_ms, guard, request_id}` | fim do turno |
| `error` | `{code, message, retryable}` | falha no meio do turno (o status HTTP ja foi 200) |

O texto final e sempre o autoritativo: se chegar `guard`, o que veio antes em `token` deve ser
descartado.

Limites: `X-RateLimit-*` em toda resposta; `429` com `Retry-After` quando a janela de mensagens
estoura ou o orcamento de tokens acaba. `400` quando a mensagem passa de 800 caracteres."""


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _history(mensagens: list[dict[str, Any]]) -> list[Any]:
    """Historico so com a conversa: resultados de ferramenta ficam fora do contexto."""
    history: list[Any] = []
    for item in mensagens:
        if item["role"] == "user":
            history.append(HumanMessage(str(item["content"])))
        elif item["role"] == "assistant":
            history.append(AIMessage(str(item["content"])))
    return history


def _rate_headers(limit: int, used: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(limit - used, 0)),
        "X-RateLimit-Reset": "60",
    }


def _stream_headers(extras: dict[str, str]) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        **extras,
    }


@router.post(
    "/chat",
    summary="Envia uma mensagem e recebe a resposta em streaming",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Eventos SSE"},
        400: {"model": ErrorResponse, "description": "Mensagem acima de 800 caracteres"},
        401: {
            "model": ErrorResponse,
            "description": "Token ausente, invalido, revogado ou expirado",
        },
        429: {
            "model": ErrorResponse,
            "description": "Rate limit da sessao ou orcamento de tokens esgotado",
        },
    },
    description=SSE_DOC,
)
async def chat(
    payload: ChatRequest,
    session: Annotated[Session, Depends(require_session)],
    store: Annotated[RuntimeStore, Depends(get_store)],
    runner: Annotated[AgentRunner, Depends(get_runner)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    request_id = uuid4().hex[:12]
    limit = settings.max_messages_per_minute
    window = store.recent_turns(session.session_id, 60)
    headers = _stream_headers(_rate_headers(limit, window + 1))

    if window >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": f"Calma ai! Voce chegou ao limite de {limit} mensagens por minuto.",
            },
            headers={"Retry-After": "60", **_rate_headers(limit, window)},
        )

    verdict = screen(payload.message)
    if verdict.code == "message_too_long":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": verdict.code, "message": verdict.response},
        )

    spent = store.usage(session)
    headers["X-Budget-Remaining"] = str(spent["remaining"])
    if int(spent["remaining"]) <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "budget_exhausted",
                "message": "O orcamento de tokens desta sessao acabou. Abra uma nova sessao.",
            },
            headers={"Retry-After": "0", **headers},
        )

    if not verdict.allowed:
        return _blocked_response(store, session, payload.message, verdict, settings)

    store.append_message(session.session_id, role="user", content=payload.message)
    history = _history(store.messages(session.session_id)[:-1])
    agent_session = SessionContext(
        customer_id=session.customer_id, customer_name=session.customer_name
    )

    async def events() -> AsyncIterator[str]:
        started = time.perf_counter()
        accumulator = TurnAccumulator()
        conn = connect(settings.database_path)
        try:
            async for event in runner.stream(
                agent_session, history, payload.message, accumulator, conn
            ):
                yield _sse(event["event"], event["data"])

            latency = int((time.perf_counter() - started) * 1000)
            outcome = accumulator.to_outcome(latency_ms=latency)

            store.bind_customer(
                session.session_id, agent_session.customer_id, agent_session.customer_name
            )
            message_id = store.append_message(
                session.session_id,
                role="assistant",
                content=outcome.answer,
                guard=outcome.guard,
                latency_ms=latency,
            )
            store.add_usage(session.session_id, outcome)

            if settings.audit_enabled:
                audit_event(
                    logs_dir=settings.logs_dir,
                    request_id=request_id,
                    session_id=session.session_id,
                    customer_id=agent_session.customer_id,
                    message=payload.message,
                    outcome=outcome,
                )

            yield _sse("usage", store.usage(session))
            yield _sse(
                "done",
                {
                    "message_id": message_id,
                    "latency_ms": latency,
                    "guard": outcome.guard,
                    "request_id": request_id,
                },
            )
        except Exception:
            # o status HTTP ja foi enviado; a falha vai como evento, nao como stack trace
            logger.exception("falha no turno %s da sessao %s", request_id, session.session_id)
            yield _sse(
                "error",
                {
                    "code": "turn_failed",
                    "message": "Nao consegui concluir agora. Tente de novo em instantes.",
                    "retryable": True,
                    "request_id": request_id,
                },
            )
        finally:
            conn.close()

    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


def _blocked_response(
    store: RuntimeStore,
    session: Session,
    message: str,
    verdict: Verdict,
    settings: Settings,
) -> StreamingResponse:
    """Guard de entrada atuou: responde sem chamar o provedor e registra o motivo."""
    request_id = uuid4().hex[:12]
    limit = settings.max_messages_per_minute
    window = store.recent_turns(session.session_id, 60)
    headers = _stream_headers(_rate_headers(limit, window + 1))

    async def events() -> AsyncIterator[str]:
        store.append_message(session.session_id, role="user", content=message)
        yield _sse("guard", {"tipo": verdict.code, "acao": "responder_fixo"})
        yield _sse("token", {"delta": verdict.response or ""})

        outcome = TurnOutcome(
            answer=verdict.response or "",
            guard=verdict.code,
            prompt_version="guard",
            model=settings.llm_model,
        )
        message_id = store.append_message(
            session.session_id,
            role="assistant",
            content=outcome.answer,
            guard=outcome.guard,
        )

        if settings.audit_enabled:
            audit_event(
                logs_dir=settings.logs_dir,
                request_id=request_id,
                session_id=session.session_id,
                customer_id=session.customer_id,
                message=message,
                outcome=outcome,
            )

        yield _sse("usage", store.usage(session))
        yield _sse(
            "done",
            {
                "message_id": message_id,
                "latency_ms": 0,
                "guard": outcome.guard,
                "request_id": request_id,
            },
        )

    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)