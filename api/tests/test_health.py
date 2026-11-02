import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "database_path": tmp_path / "loja.db",
        "data_dir": tmp_path / "data",
        "logs_dir": tmp_path / "logs",
        "deepseek_api_key": None,
        "openai_api_key": None,
        "anthropic_api_key": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_healthz_is_independent_of_storage(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_all_checks(client: TestClient) -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["storage"] is True
    assert body["checks"]["database"] is True


def test_readyz_does_not_count_empty_key_as_configured(client: TestClient) -> None:
    """Regressao do GATE 0: chave vazia nao e chave configurada."""
    body = client.get("/readyz").json()

    assert body["checks"]["llm_configured"] is False


def test_meta_exposes_provider_without_secrets(client: TestClient) -> None:
    response = client.get("/v1/meta")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"]
    assert body["model"]
    assert body["app_version"]
    assert "api_key" not in response.text.lower()
    assert "sk-" not in response.text.lower()


def test_meta_never_echoes_the_configured_key(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    import app.main as main_module

    segredo = "sk-segredo-que-nao-pode-vazar"
    monkeypatch.setattr(main_module, "settings", _settings(tmp_path, deepseek_api_key=segredo))

    response = client.get("/v1/meta")

    assert response.json()["llm_configured"] is True
    assert segredo not in response.text


def test_readyz_fails_when_database_is_missing(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    import app.api.health as health_module

    monkeypatch.setattr(health_module, "get_settings", lambda: _settings(tmp_path))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["storage"] is True
    assert response.json()["checks"]["database"] is False


def test_readyz_fails_when_storage_is_missing(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    import app.api.health as health_module

    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: _settings(tmp_path, database_path=tmp_path / "ausente" / "loja.db"),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["storage"] is False


def test_readyz_fails_when_database_has_no_schema(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    import app.api.health as health_module

    vazio = tmp_path / "vazio.db"
    sqlite3.connect(vazio).close()
    monkeypatch.setattr(health_module, "get_settings", lambda: _settings(tmp_path))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False


def test_readyz_fails_when_database_file_is_corrupt(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    import app.api.health as health_module

    (tmp_path / "loja.db").write_bytes(b"isto nao e um banco sqlite")
    monkeypatch.setattr(health_module, "get_settings", lambda: _settings(tmp_path))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False
