from fastapi.testclient import TestClient

ORIGEM = "http://localhost:5173"


def test_cors_libera_origem_de_desenvolvimento(client: TestClient) -> None:
    resposta = client.get("/v1/meta", headers={"Origin": ORIGEM})

    assert resposta.headers["access-control-allow-origin"] == ORIGEM


def test_cors_nao_libera_origem_desconhecida(client: TestClient) -> None:
    resposta = client.get("/v1/meta", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in resposta.headers


def test_cors_expoe_cabecalhos_de_limite_ao_navegador(client: TestClient) -> None:
    resposta = client.get("/v1/meta", headers={"Origin": ORIGEM})
    expostos = resposta.headers.get("access-control-expose-headers", "")

    assert "X-RateLimit-Limit" in expostos
    assert "X-Budget-Remaining" in expostos


def test_cors_aceita_preflight_do_chat(client: TestClient) -> None:
    resposta = client.options(
        "/v1/chat",
        headers={
            "Origin": ORIGEM,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == ORIGEM
    assert "authorization" in resposta.headers["access-control-allow-headers"].lower()
