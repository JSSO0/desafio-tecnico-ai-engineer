"""Seam do agente: o que fazemos com o que o framework devolve.

Nao testamos o loop ReAct do LangChain (codigo de terceiro, coberto a montante). Testamos a
nossa extracao: quais tools foram chamadas, quanto token entrou, qual texto e a resposta final
e quando o gate de preco substitui a resposta.
"""

from types import SimpleNamespace

from app.agent.agent import message_text, run_turn
from app.agent.prompts import active_prompt_version
from app.guards.grounding import FALLBACK


class FakeAgent:
    def __init__(self, messages: list[SimpleNamespace]) -> None:
        self.messages = messages
        self.payload = None

    def invoke(self, payload):
        self.payload = payload
        return {"messages": self.messages}


def ai(content, *, tool_calls=None, tokens=(0, 0)):
    return SimpleNamespace(
        type="ai",
        content=content,
        tool_calls=tool_calls or [],
        usage_metadata={"input_tokens": tokens[0], "output_tokens": tokens[1]},
    )


def tool(content, *, tokens=(0, 0)):
    return SimpleNamespace(
        type="tool",
        content=content,
        tool_calls=[],
        usage_metadata={"input_tokens": tokens[0], "output_tokens": tokens[1]},
    )


def test_turn_extracts_tools_tokens_and_answer() -> None:
    agente = FakeAgent(
        [
            ai(
                "",
                tool_calls=[{"name": "detalhe_produto", "args": {"nome_ou_id": "95"}}],
                tokens=(10, 5),
            ),
            tool('{"preco": "R$ 2.199,00"}'),
            ai("O Takamine GD20 custa R$ 2.199,00.", tokens=(20, 8)),
        ]
    )

    resultado = run_turn(agente, [], "quanto custa o Takamine GD20?")

    assert resultado.answer == "O Takamine GD20 custa R$ 2.199,00."
    assert resultado.raw_answer == resultado.answer
    assert resultado.guard is None
    assert resultado.tools_used == ["detalhe_produto"]
    assert resultado.tool_calls[0]["args"] == {"nome_ou_id": "95"}
    assert (resultado.tokens_in, resultado.tokens_out) == (30, 13)
    assert resultado.prompt_version == active_prompt_version()


def test_turn_blocks_price_without_tool_support() -> None:
    agente = FakeAgent([ai("Sai por R$ 1.499,00.", tokens=(5, 5))])

    resultado = run_turn(agente, [], "quanto custa?")

    assert resultado.guard == "preco_sem_ferramenta"
    assert resultado.answer == FALLBACK
    assert "1.499" in resultado.raw_answer, "a resposta original fica registrada para auditoria"


def test_turn_uses_last_answer_without_tool_calls() -> None:
    agente = FakeAgent(
        [
            ai("Deixa eu consultar.", tool_calls=[{"name": "buscar_produtos", "args": {}}]),
            tool('{"total_encontrado": 0}'),
            ai("Nao encontrei esse modelo no catalogo."),
        ]
    )

    resultado = run_turn(agente, [], "tem saxofone?")

    assert resultado.answer == "Nao encontrei esse modelo no catalogo."
    assert resultado.tools_used == ["buscar_produtos"]


def test_turn_grounds_value_found_in_any_tool_output() -> None:
    agente = FakeAgent(
        [
            ai(
                "",
                tool_calls=[
                    {"name": "buscar_produtos", "args": {}},
                    {"name": "simular_pagamento", "args": {}},
                ],
            ),
            tool('{"total_encontrado": 12}'),
            tool('{"valor_final": "R$ 1.900,00"}'),
            ai("No pix fica R$ 1.900,00."),
        ]
    )

    resultado = run_turn(agente, [], "e no pix?")

    assert resultado.guard is None
    assert resultado.tools_used == ["buscar_produtos", "simular_pagamento"]


def test_turn_forwards_history_and_current_message() -> None:
    agente = FakeAgent([ai("Oi! Como posso ajudar?")])

    run_turn(agente, [ai("turno anterior")], "bom dia")

    enviadas = agente.payload["messages"]
    assert len(enviadas) == 2
    assert enviadas[-1].content == "bom dia"


def test_message_text_accepts_string_and_blocks() -> None:
    assert message_text("texto") == "texto"
    assert message_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    assert message_text([{"type": "tool_use", "id": "x"}, "solto"]) == "solto"
    assert message_text(None) == ""
