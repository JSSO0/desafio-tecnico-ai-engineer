import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.runtime.store import RuntimeStore


def _abrir_sessao(client: TestClient) -> tuple[str, str]:
    resposta = client.post("/v1/sessions")
    assert resposta.status_code == 201
    corpo = resposta.json()
    return corpo["access_token"], corpo["session_id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_abre_sessao_com_token_opaco(client: TestClient) -> None:
    token, session_id = _abrir_sessao(client)

    assert len(token) >= 40
    assert session_id
    assert token.count(".") != 2, "token opaco, nao JWT"


def test_usage_sem_token_e_401(client: TestClient) -> None:
    resposta = client.get("/v1/sessions/qualquer/usage")

    assert resposta.status_code == 401
    assert resposta.json()["detail"]["code"] == "missing_token"


def test_token_desconhecido_e_401(client: TestClient) -> None:
    resposta = client.get("/v1/sessions/qualquer/usage", headers=_auth("nao-existe"))

    assert resposta.status_code == 401
    assert resposta.json()["detail"]["code"] == "invalid_token"


def test_usage_inicial_zerado(client: TestClient) -> None:
    token, session_id = _abrir_sessao(client)

    resposta = client.get(f"/v1/sessions/{session_id}/usage", headers=_auth(token))
    corpo = resposta.json()

    assert resposta.status_code == 200
    assert corpo["tokens_total"] == 0
    assert corpo["remaining"] == corpo["budget_tokens"]


def test_token_nao_acessa_outra_sessao(client: TestClient) -> None:
    token, _ = _abrir_sessao(client)
    _, outra = _abrir_sessao(client)

    resposta = client.get(f"/v1/sessions/{outra}/usage", headers=_auth(token))

    assert resposta.status_code == 404
    assert resposta.json()["detail"]["code"] == "session_not_found"


def test_encerrar_revoga_token_e_apaga_historico(client: TestClient) -> None:
    token, session_id = _abrir_sessao(client)
    client.post("/v1/chat", json={"message": "oi"}, headers=_auth(token))

    encerrar = client.delete(f"/v1/sessions/{session_id}", headers=_auth(token))
    depois = client.get(f"/v1/sessions/{session_id}/usage", headers=_auth(token))
    historico = client.get(f"/v1/sessions/{session_id}/messages", headers=_auth(token))

    assert encerrar.status_code == 204
    assert depois.status_code == 401
    assert depois.json()["detail"]["code"] == "revoked_token"
    assert historico.status_code == 401


def test_token_expirado_e_401(
    client: TestClient, store: RuntimeStore, tmp_path: Path
) -> None:
    token, session_id = _abrir_sessao(client)
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            ("2020-01-01T00:00:00+00:00", session_id),
        )
        conn.commit()

    resposta = client.get(f"/v1/sessions/{session_id}/usage", headers=_auth(token))

    assert resposta.status_code == 401
    assert resposta.json()["detail"]["code"] == "expired_token"
