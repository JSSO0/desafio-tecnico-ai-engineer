from __future__ import annotations


class EmporioError(Exception):
    """Base das falhas de dominio.

    Existe para o chamador poder capturar esta familia sem capturar qualquer coisa: um
    `except Exception` esconde bug, um `except EmporioError` trata o que foi previsto.
    """


class DataSourceError(EmporioError):
    """Dado de origem ausente, duplicado ou invalido: CSV, JSON de specs, arquivo de politica."""


class SessionError(EmporioError):
    """Falha de sessao com o codigo que a API devolve ao cliente."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message