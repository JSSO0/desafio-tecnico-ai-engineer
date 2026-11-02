"""Ambiente dos testes: roda fora do container, sem rede, sem chave e sem tocar os dados de origem.

As variaveis precisam ser definidas antes de qualquer import de `app` porque `Settings` e
`app.main` leem o ambiente no import. Por isso o bloco abaixo nao depende de fixture.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from contextlib import closing
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
POLICIES_DIR = DATA_DIR / "policies"

_TMP = Path(tempfile.mkdtemp(prefix="emporio-testes-"))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATA_DIR": str(DATA_DIR),
        "DATABASE_PATH": str(_TMP / "loja.db"),
        "RUNTIME_PATH": str(_TMP / "runtime.db"),
        "LOGS_DIR": str(_TMP / "logs"),
        "LLM_PROVIDER": "deepseek",
        "LLM_MODEL": "deepseek-chat",
        "DEEPSEEK_API_KEY": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
    }
)

atexit.register(shutil.rmtree, _TMP, True)


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def policies_dir() -> Path:
    return POLICIES_DIR


@pytest.fixture(scope="session")
def db_path() -> Path:
    """Base canonica, construida uma vez por sessao a partir dos CSVs de origem."""
    from app.db.build import build_database

    path = Path(os.environ["DATABASE_PATH"])
    build_database(path, DATA_DIR, POLICIES_DIR)
    return path


@pytest.fixture(scope="session")
def conn(db_path: Path):
    """Conexao somente leitura, igual a usada pelas ferramentas do agente."""
    from app.db.connection import connect

    with closing(connect(db_path)) as connection:
        yield connection


@pytest.fixture(scope="session")
def client(db_path: Path):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def settings():
    from app.core.config import get_settings

    return get_settings()


@pytest.fixture(scope="session")
def store():
    """Mesmo estado de execucao que a API usa: sessoes, historico e consumo."""
    from app.runtime.store import RuntimeStore

    return RuntimeStore(Path(os.environ["RUNTIME_PATH"]))
