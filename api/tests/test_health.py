import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # context manager para o lifespan rodar: e ele que constroi a base quando ela nao existe
    with TestClient(app) as test_client:
        yield test_client


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_checks(client: TestClient) -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["storage"] is True
    assert body["checks"]["database"] is True
    assert "llm_configured" in body["checks"]


def test_meta_exposes_provider_without_secrets(client: TestClient) -> None:
    response = client.get("/v1/meta")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"]
    assert body["model"]
    assert "api_key" not in response.text.lower()
