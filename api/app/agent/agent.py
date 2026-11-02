from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage

from app.agent.prompts import active_prompt_version, load_prompt
from app.agent.session import SessionContext
from app.core.config import Settings, get_settings
from app.guards.grounding import enforce_price_grounding
from app.tools import build_tools


@dataclass
class TurnResult:
    answer: str
    raw_answer: str
    tool_calls: list[dict[str, Any]]
    tool_output: str
    tokens_in: int
    tokens_out: int
    guard: str | None
    prompt_version: str
    messages: list[Any]

    @property
    def tools_used(self) -> list[str]:
        return [str(call.get("name")) for call in self.tool_calls]


def build_model(settings: Settings | None = None):
    settings = settings or get_settings()
    return init_chat_model(
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        temperature=settings.llm_temperature,
    )


def build_agent(session: SessionContext, conn: sqlite3.Connection, *, model: Any = None):
    return create_agent(
        model=model or build_model(),
        tools=build_tools(session, conn),
        system_prompt=load_prompt(),
        name="emporio-atendimento",
    )


def message_text(content: Any) -> str:
    """Conteudo de mensagem pode ser str ou lista de blocos, dependendo do provedor."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = []
        for bloco in content:
            if isinstance(bloco, str):
                partes.append(bloco)
            elif isinstance(bloco, dict) and bloco.get("type") in {"text", "text_delta"}:
                partes.append(str(bloco.get("text", "")))
        return "".join(partes)
    return str(content or "")


def run_turn(agent: Any, history: list[Any], message: str) -> TurnResult:
    result = agent.invoke({"messages": [*history, HumanMessage(message)]})
    messages = list(result["messages"])

    tool_calls: list[dict[str, Any]] = []
    tool_output: list[str] = []
    tokens_in = tokens_out = 0
    answer = ""

    for item in messages:
        for call in getattr(item, "tool_calls", None) or []:
            tool_calls.append({"name": call.get("name"), "args": call.get("args")})
        if getattr(item, "type", "") == "tool":
            tool_output.append(message_text(item.content))
        usage = getattr(item, "usage_metadata", None) or {}
        tokens_in += int(usage.get("input_tokens", 0) or 0)
        tokens_out += int(usage.get("output_tokens", 0) or 0)
        if getattr(item, "type", "") == "ai" and not (getattr(item, "tool_calls", None) or []):
            answer = message_text(item.content)

    guardado, guard = enforce_price_grounding(answer, "\n".join(tool_output))

    # O historico guarda a conversa, nao os resultados de ferramenta: reenviar todos os payloads
    # a cada turno faz o contexto crescer sem limite (13k tokens no terceiro turno). O agente
    # reconsulta quando precisa — e barato e o dado vem sempre atualizado. O que ficou de fora
    # continua no log de auditoria.
    historico = [HumanMessage(message), AIMessage(guardado)]

    return TurnResult(
        answer=guardado,
        raw_answer=answer,
        tool_calls=tool_calls,
        tool_output="\n".join(tool_output),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        guard=guard,
        prompt_version=active_prompt_version(),
        messages=historico,
    )
