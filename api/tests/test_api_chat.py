import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_runner
from app.core.turn import TurnOutcome
from app.main import app
from app.runtime.store import RuntimeStore


class FakeRunner:
    """Agente roteirizado: exercita a API sem chamar provedor nenhum."""

    def __init__(self, text: str = "O violao sai por R$ 599,90.", guard: str | None = None):
        self.text = text
        self.guard = guard
        self.historico: list[Any] = []

    async def stream(self, ctx, history, message, acc, conn):
        self.historico = list(history)
        acc.tool_calls.append({"name": "buscar_produtos", "args": {"termo": "violao"}})
        yield {
            "event": "tool_call",
            "data": {"name": "buscar_produtos", "args": {}, "status": "start"},
        }
        yield {"event": "card", "data": {"tipo": "produto", "dados": {"nome": "Yamaha C40"}}}
        yield {"event": "token", "data": {"delta": self.text[:10]}}
        yield {"event": "token", "data": {"delta": self.text[10:]}}
        acc.tokens_in = 1200
        acc.tokens_out = 80
        acc.raw_answer = self.text
        acc.answer = self.text
        acc.guard = self.guard
        if self.guard:
            yield {
                "event": "guard",
                "data": {"tipo": self.guard, "acao": "substituir_resposta", "texto": self.text},
            }


def _eventos(response) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in response.text.strip().split("\n\n"):
        campos = {}
        for line in bloco.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                campos[key] = value
        if "event" in campos:
            eventos.append((campos["event"], json.loads(campos["data"])))
    return eventos


@pytest.fixture
def runner():
    fake = FakeRunner()
    app.dependency_overrides[get_runner] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def _session(client: TestClient) -> tuple[str, str]:
    corpo = client.post("/v1/sessions").json()
    return corpo["access_token"], corpo["session_id"]


def test_chat_exige_token(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"message": "oi"})

    assert response.status_code == 401


def test_chat_emite_stream_e_fecha_com_done(client: TestClient, runner) -> None:
    token, _ = _session(client)

    response = client.post(
        "/v1/chat",
        json={"message": "tem violao?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eventos = _eventos(response)

    nomes = [name for name, _ in eventos]
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert nomes[0] == "tool_call"
    assert "card" in nomes
    assert nomes.count("token") == 2
    assert nomes[-1] == "done"
    assert "usage" in nomes


def test_texto_concatenado_dos_tokens_e_a_resposta(client: TestClient, runner) -> None:
    token, session_id = _session(client)

    eventos = _eventos(
        client.post(
            "/v1/chat",
            json={"message": "tem violao?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    )
    text = "".join(data["delta"] for name, data in eventos if name == "token")

    historico = client.get(
        f"/v1/sessions/{session_id}/messages", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert text == runner.text
    assert [item["role"] for item in historico["messages"]] == ["user", "assistant"]
    assert historico["messages"][1]["content"] == runner.text


def test_usage_cresce_depois_do_turno(client: TestClient, runner) -> None:
    token, session_id = _session(client)

    client.post("/v1/chat", json={"message": "oi"}, headers={"Authorization": f"Bearer {token}"})
    corpo = client.get(
        f"/v1/sessions/{session_id}/usage", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert corpo["tokens_in"] == 1200
    assert corpo["tokens_out"] == 80
    assert corpo["turnos"] == 1
    assert corpo["remaining"] == corpo["budget_tokens"] - 1280


def test_guard_vai_no_evento_e_na_mensagem_persistida(client: TestClient) -> None:
    fake = FakeRunner(
        text="Deixa eu confirmar esses valores no sistema, ta?",
        guard="preco_sem_ferramenta",
    )
    app.dependency_overrides[get_runner] = lambda: fake
    token, session_id = _session(client)

    eventos = _eventos(
        client.post(
            "/v1/chat",
            json={"message": "quanto custa?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    )
    done = next(data for name, data in eventos if name == "done")
    historico = client.get(
        f"/v1/sessions/{session_id}/messages", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert "guard" in [name for name, _ in eventos]
    assert done["guard"] == "preco_sem_ferramenta"
    assert historico["messages"][1]["guard"] == "preco_sem_ferramenta"
    app.dependency_overrides.clear()


def test_historico_anterior_e_enviado_ao_agente(client: TestClient, runner) -> None:
    token, _ = _session(client)
    cabecalho = {"Authorization": f"Bearer {token}"}

    client.post("/v1/chat", json={"message": "primeira"}, headers=cabecalho)
    client.post("/v1/chat", json={"message": "segunda"}, headers=cabecalho)

    assert len(runner.historico) == 2
    assert runner.historico[0].content == "primeira"
    assert runner.historico[1].content == runner.text


def test_orcamento_esgotado_devolve_429(
    client: TestClient, runner, store: RuntimeStore
) -> None:
    token, session_id = _session(client)
    store.add_usage(session_id, TurnOutcome(answer="", tokens_in=10_000_000))

    response = client.post(
        "/v1/chat", json={"message": "oi"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "budget_exhausted"
