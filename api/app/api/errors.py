from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import EmporioError

logger = logging.getLogger(__name__)


def _payload(code: str, request_id: str) -> dict[str, str]:
    return {
        "code": code,
        "message": "Nao consegui concluir agora. Tente de novo em instantes.",
        "request_id": request_id,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Erro inesperado vira JSON com request_id, nunca traceback para o cliente.

    Nao existe try/except "por garantia" espalhado pelo codigo: so se captura onde ha decisao a
    tomar. Aqui a decisao e a da borda — responder sem vazar detalhe e correlacionar com o log.
    """

    @app.exception_handler(EmporioError)
    async def _domain_error(request: Request, exc: EmporioError) -> JSONResponse:
        request_id = uuid4().hex[:12]
        logger.error(
            "erro de dominio %s em %s %s: %s",
            request_id,
            request.method,
            request.url.path,
            exc,
            exc_info=exc,
        )
        return JSONResponse(status_code=500, content=_payload("domain_error", request_id))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = uuid4().hex[:12]
        logger.error(
            "erro nao tratado %s em %s %s",
            request_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(status_code=500, content=_payload("internal_error", request_id))