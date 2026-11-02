"""Cliente HTTP minimo da API. Usado pela avaliacao e pelo gerador de conversas.

Antes cada script tinha a sua copia da abertura de sessao e do parsing de SSE; qualquer mudanca no
formato dos eventos precisava ser feita duas vezes. Aqui o protocolo mora em um lugar so.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def request(url: str, payload: dict[str, Any] | None = None, token: str | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    metodo = "POST" if data else "GET"
    req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
    return urllib.request.urlopen(req, timeout=180)


def open_session(base_url: str) -> str:
    with request(f"{base_url}/v1/sessions", {}) as response:
        return json.loads(response.read())["access_token"]


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for bloco in body.strip().split("\n\n"):
        fields: dict[str, str] = {}
        for linha in bloco.splitlines():
            if ": " in linha:
                key, value = linha.split(": ", 1)
                fields[key] = value
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


def say(base_url: str, token: str, message: str) -> dict[str, Any]:
    """Um turno completo: texto concatenado, ferramentas iniciadas, guard e request_id."""
    with request(f"{base_url}/v1/chat", {"message": message}, token) as response:
        body = response.read().decode("utf-8")

    text: list[str] = []
    tools: list[str] = []
    guard = None
    request_id = None

    for evento, dados in parse_sse(body):
        if evento == "token":
            text.append(dados.get("delta", ""))
        elif evento == "tool_call":
            if dados.get("status") == "start" and dados.get("name"):
                tools.append(dados["name"])
        elif evento == "guard":
            guard = dados.get("tipo")
        elif evento == "done":
            guard = dados.get("guard") or guard
            request_id = dados.get("request_id")

    return {"texto": "".join(text), "tools": tools, "guard": guard, "request_id": request_id}