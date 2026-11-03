from fastapi.testclient import TestClient

ORIGEM = "http://localhost:5173"


def test_cors_libera_origem_de_desenvolvimento(client: TestClient) -> None:
    response = client.get("/v1/meta", headers={"Origin": ORIGEM})

    assert response.headers["access-control-allow-origin"] == ORIGEM


def test_cors_nao_libera_origem_desconhecida(client: TestClient) -> None:
    response = client.get("/v1/meta", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_expoe_cabecalhos_de_limite_ao_navegador(client: TestClient) -> None:
    response = client.get("/v1/meta", headers={"Origin": ORIGEM})
    expostos = response.headers.get("access-control-expose-headers", "")

    assert "X-RateLimit-Limit" in expostos
    assert "X-Budget-Remaining" in expostos


def test_cors_aceita_preflight_do_chat(client: TestClient) -> None:
    response = client.options(
        "/v1/chat",
        headers={
            "Origin": ORIGEM,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGEM
    assert "authorization" in response.headers["access-control-allow-headers"].lower()

def test_cors_libera_origem_do_container(client: TestClient) -> None:
    origin = "http://localhost:8080"

    response = client.get("/v1/meta", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin
