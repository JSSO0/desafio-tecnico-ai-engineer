from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain.messages import AIMessageChunk, HumanMessage

from app.agent.agent import build_agent, message_text
from app.agent.prompts import active_prompt_version
from app.agent.session import SessionContext
from app.core.config import get_settings
from app.core.turn import TurnOutcome
from app.guards.grounding import enforce_price_grounding

_CARD_TOOLS = {
    "buscar_produtos": "produto",
    "detalhe_produto": "produto",
    "consultar_pedido": "pedido",
    "consultar_politicas": "politica",
    "simular_pagamento": "pagamento",
}


@dataclass
class TurnAccumulator:
    """O que o turno produziu. Preenchido durante o streaming, lido depois para persistir."""

    answer: str = ""
    raw_answer: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_output: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    guard: str | None = None
    prompt_version: str = field(default_factory=active_prompt_version)
    model: str = ""

    @property
    def tools_used(self) -> list[str]:
        return [str(call.get("name")) for call in self.tool_calls]

    def to_outcome(self, latency_ms: int = 0) -> TurnOutcome:
        return TurnOutcome(
            answer=self.answer,
            tools=tuple(self.tools_used),
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            latency_ms=latency_ms,
            guard=self.guard,
            prompt_version=self.prompt_version,
            model=self.model,
        )


def _card(tool_name: str, content: str) -> dict[str, Any] | None:
    kind = _CARD_TOOLS.get(tool_name)
    if kind is None:
        return None
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {"tipo": kind, "dados": None}
    if not isinstance(data, dict):
        return {"tipo": kind, "dados": None}
    return {"tipo": kind, "dados": data}


class AgentRunner:
    """Executa um turno e emite eventos. Tokens saem em streaming, de verdade.

    O gate de preco roda no fim, depois de os tokens ja terem saido. Por isso, quando ele
    bloqueia, emitimos `guard` com a acao `substituir_resposta` e o texto seguro: o cliente
    deve trocar o que ja renderizou. O texto final e sempre o autoritativo.
    """

    async def stream(
        self,
        session_ctx: SessionContext,
        history: list[Any],
        message: str,
        acc: TurnAccumulator,
        conn: sqlite3.Connection,
    ) -> AsyncIterator[dict[str, Any]]:
        acc.model = get_settings().llm_model
        agent = build_agent(session_ctx, conn)
        parts: list[str] = []
        names_by_id: dict[str, str] = {}
        emitted: set[str] = set()

        async for chunk, _meta in agent.astream(
            {"messages": [*history, HumanMessage(message)]},
            stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk):
                usage = getattr(chunk, "usage_metadata", None) or {}
                acc.tokens_in += int(usage.get("input_tokens", 0) or 0)
                acc.tokens_out += int(usage.get("output_tokens", 0) or 0)

                # chunks trazem fragmentos de tool call: descarta os sem nome e nao repete o id
                calls = [call for call in (chunk.tool_calls or []) if call.get("name")]
                if calls:
                    parts.clear()  # texto antes de uma chamada nao e resposta final
                    for call in calls:
                        name = str(call["name"])
                        key = str(call.get("id") or f"{name}:{len(call.get('args') or {})}")
                        if key in emitted:
                            continue
                        emitted.add(key)
                        if call.get("id"):
                            names_by_id[str(call["id"])] = name
                        acc.tool_calls.append({"name": name, "args": call.get("args")})
                        yield {
                            "event": "tool_call",
                            "data": {
                                "name": name,
                                "args": call.get("args") or {},
                                "status": "start",
                            },
                        }

                text = message_text(chunk.content)
                if text:
                    parts.append(text)
                    yield {"event": "token", "data": {"delta": text}}

            elif getattr(chunk, "type", "") == "tool":
                payload = message_text(chunk.content)
                acc.tool_output.append(payload)
                name = names_by_id.get(str(getattr(chunk, "tool_call_id", "")), "")
                yield {
                    "event": "tool_call",
                    "data": {"name": name, "args": {}, "status": "end"},
                }
                card = _card(name, payload)
                if card is not None:
                    yield {"event": "card", "data": card}

        acc.raw_answer = "".join(parts).strip()
        acc.answer, acc.guard = enforce_price_grounding(
            acc.raw_answer, "\n".join(acc.tool_output)
        )

        if acc.guard:
            yield {
                "event": "guard",
                "data": {
                    "tipo": acc.guard,
                    "acao": "substituir_resposta",
                    "texto": acc.answer,
                },
            }
