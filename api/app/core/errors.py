from __future__ import annotations


class EmporioError(Exception):
    """Base das falhas de dominio.

    Existe para o chamador poder capturar esta familia sem capturar qualquer coisa: um
    `except Exception` esconde bug, um `except EmporioError` trata o que foi previsto.
    """


class DataSourceError(EmporioError):
    """Missing, duplicated or invalid source data: CSV, specs JSON, policy file."""


class SessionError(EmporioError):
    """Session failure carrying the code the API returns to the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
