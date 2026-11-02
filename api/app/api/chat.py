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
    historico: list[Any] = []
    for item in mensagens:
        if item["role"] == "user":
            historico.append(HumanMessage(str(item["content"])))
        elif item["role"] == "assistant":
            historico.append(AIMessage(str(item["content"])))
    return historico


def _rate_headers(limite: int, usados: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(limite),
        "X-RateLimit-Remaining": str(max(limite - usados, 0)),
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
    limite = settings.max_messages_per_minute
    janela = store.recent_turns(session.session_id, 60)
    headers = _stream_headers(_rate_headers(limite, janela + 1))

    if janela >= limite:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": f"Calma ai! Voce chegou ao limite de {limite} mensagens por minuto.",
            },
            headers={"Retry-After": "60", **_rate_headers(limite, janela)},
        )

    veredito = screen(payload.message)
    if veredito.code == "message_too_long":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": veredito.code, "message": veredito.response},
        )

    consumo = store.usage(session)
    headers["X-Budget-Remaining"] = str(consumo["remaining"])
    if int(consumo["remaining"]) <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "budget_exhausted",
                "message": "O orcamento de tokens desta sessao acabou. Abra uma nova sessao.",
            },
            headers={"Retry-After": "0", **headers},
        )

    if not veredito.allowed:
        return _blocked_response(
            store, session, payload.message, veredito, settings, request_id, headers
        )

    store.append_message(session.session_id, role="user", content=payload.message)
    historico = _history(store.messages(session.session_id)[:-1])
    contexto = SessionContext(customer_id=session.customer_id, customer_name=session.customer_name)

    async def eventos() -> AsyncIterator[str]:
        inicio = time.perf_counter()
        acumulado = TurnAccumulator()
        conn = connect(settings.database_path)
        try:
            async for evento in runner.stream(
                contexto, historico, payload.message, acumulado, conn
            ):
                yield _sse(evento["event"], evento["data"])

            latencia = int((time.perf_counter() - inicio) * 1000)
            store.bind_customer(
                session.session_id, contexto.customer_id, contexto.customer_name
            )
            message_id = store.append_message(
                session.session_id,
                role="assistant",
                content=acumulado.answer,
                guard=acumulado.guard,
                latency_ms=latencia,
            )
            store.add_usage(
                session.session_id,
                tokens_in=acumulado.tokens_in,
                tokens_out=acumulado.tokens_out,
                tools=acumulado.tools_used,
                guard=acumulado.guard,
                latency_ms=latencia,
                prompt_version=acumulado.prompt_version,
                model=settings.llm_model,
            )
            if settings.audit_enabled:
                audit_event(
                    logs_dir=settings.logs_dir,
                    request_id=request_id,
                    session_id=session.session_id,
                    customer_id=contexto.customer_id,
                    message=payload.message,
                    tools=acumulado.tools_used,
                    guard=acumulado.guard,
                    tokens_in=acumulado.tokens_in,
                    tokens_out=acumulado.tokens_out,
                    latency_ms=latencia,
                    prompt_version=acumulado.prompt_version,
                    model=settings.llm_model,
                )
            yield _sse("usage", store.usage(session))
            yield _sse(
                "done",
                {
                    "message_id": message_id,
                    "latency_ms": latencia,
                    "guard": acumulado.guard,
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

    return StreamingResponse(eventos(), media_type="text/event-stream", headers=headers)


def _blocked_response(
    store: RuntimeStore,
    session: Session,
    message: str,
    veredito: Verdict,
    settings: Settings,
    request_id: str,
    headers: dict[str, str],
) -> StreamingResponse:
    """Guard de entrada atuou: responde sem chamar o provedor e registra o motivo."""

    async def eventos() -> AsyncIterator[str]:
        store.append_message(session.session_id, role="user", content=message)
        yield _sse("guard", {"tipo": veredito.code, "acao": "responder_fixo"})
        yield _sse("token", {"delta": veredito.response or ""})
        message_id = store.append_message(
            session.session_id,
            role="assistant",
            content=veredito.response or "",
            guard=veredito.code,
            latency_ms=0,
        )
        if settings.audit_enabled:
            audit_event(
                logs_dir=settings.logs_dir,
                request_id=request_id,
                session_id=session.session_id,
                customer_id=session.customer_id,
                message=message,
                tools=[],
                guard=veredito.code,
                tokens_in=0,
                tokens_out=0,
                latency_ms=0,
                prompt_version="guard",
                model=settings.llm_model,
            )
        yield _sse("usage", store.usage(session))
        yield _sse(
            "done",
            {
                "message_id": message_id,
                "latency_ms": 0,
                "guard": veredito.code,
                "request_id": request_id,
            },
        )

    return StreamingResponse(eventos(), media_type="text/event-stream", headers=headers)
