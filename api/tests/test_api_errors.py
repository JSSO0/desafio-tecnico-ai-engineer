from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.core.errors import DataSourceError


def _app_com_rota_que_falha(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/estoura")
    def estoura() -> None:
        raise exc

    return app


def _client(exc: Exception) -> TestClient:
    return TestClient(_app_com_rota_que_falha(exc), raise_server_exceptions=False)


def test_erro_inesperado_vira_json_com_request_id() -> None:
    resposta = _client(RuntimeError("boom")).get("/estoura")
    corpo = resposta.json()

    assert resposta.status_code == 500
    assert corpo["code"] == "internal_error"
    assert corpo["request_id"]
    assert "boom" not in resposta.text


def test_erro_de_dominio_tem_codigo_proprio_e_nao_vaza_detalhe() -> None:
    resposta = _client(DataSourceError("caminho interno X")).get("/estoura")
    corpo = resposta.json()

    assert resposta.status_code == 500
    assert corpo["code"] == "domain_error"
    assert "caminho interno X" not in resposta.text


def test_resposta_de_erro_segue_o_mesmo_formato() -> None:
    resposta = _client(RuntimeError("x")).get("/estoura")

    assert set(resposta.json()) == {"code", "message", "request_id"}