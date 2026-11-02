"""Avaliacao do agente pelo mesmo caminho da producao: HTTP + SSE.

Diferente do pytest, aqui entram o modelo real, a latencia e o tom. Os casos declaram o que
precisa aparecer, o que nao pode aparecer e quais ferramentas precisam ser usadas.

    python scripts/eval.py                       # contra http://127.0.0.1:8000
    python scripts/eval.py --json                # saida legivel por maquina
    python scripts/eval.py --ids devolucao,pix   # subconjunto
"""

from __future__ import annotations

import argparse
import json
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CASOS_PADRAO = REPO_ROOT / "evals" / "casos.jsonl"


def normalize(text: str) -> str:
    decomposto = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch)).lower()


def _request(url: str, payload: dict[str, Any] | None = None, token: str | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    metodo = "POST" if data else "GET"
    req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
    return urllib.request.urlopen(req, timeout=180)


def abrir_sessao(base_url: str) -> str:
    with _request(f"{base_url}/v1/sessions", {}) as resposta:
        return json.loads(resposta.read())["access_token"]


def falar(base_url: str, token: str, mensagem: str) -> dict[str, Any]:
    """Um turno completo: devolve texto concatenado, ferramentas e guard."""
    texto: list[str] = []
    tools: list[str] = []
    guard = None
    request_id = None

    with _request(f"{base_url}/v1/chat", {"message": mensagem}, token) as resposta:
        corpo = resposta.read().decode("utf-8")

    for bloco in corpo.strip().split("\n\n"):
        campos = {}
        for linha in bloco.splitlines():
            if ": " in linha:
                chave, valor = linha.split(": ", 1)
                campos[chave] = valor
        if "event" not in campos:
            continue

        dados = json.loads(campos["data"])
        if campos["event"] == "token":
            texto.append(dados.get("delta", ""))
        elif campos["event"] == "tool_call":
            iniciou = dados.get("status") == "start" and dados.get("name")
            if iniciou:
                tools.append(dados["name"])
        elif campos["event"] == "guard":
            guard = dados.get("tipo")
        elif campos["event"] == "done":
            guard = dados.get("guard") or guard
            request_id = dados.get("request_id")

    return {"texto": "".join(texto), "tools": tools, "guard": guard, "request_id": request_id}


def avaliar(caso: dict[str, Any], resultado: dict[str, Any]) -> list[str]:
    falhas: list[str] = []
    texto = normalize(resultado["texto"])

    for trecho in caso.get("deve_conter", []):
        if normalize(trecho) not in texto:
            falhas.append(f"faltou {trecho!r}")
    for trecho in caso.get("nao_deve_conter", []):
        if normalize(trecho) in texto:
            falhas.append(f"nao podia conter {trecho!r}")
    for tool in caso.get("tools_esperadas", []):
        if tool not in resultado["tools"]:
            falhas.append(f"nao chamou {tool}")
    if caso.get("guard_esperado") and resultado["guard"] != caso["guard_esperado"]:
        falhas.append(f"guard {resultado['guard']!r} != {caso['guard_esperado']!r}")

    return falhas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avalia o agente contra a API em execucao")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--casos", type=Path, default=CASOS_PADRAO)
    parser.add_argument("--ids", default="", help="lista separada por virgula")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    linhas = args.casos.read_text(encoding="utf-8").splitlines()
    casos = [json.loads(linha) for linha in linhas if linha.strip()]
    if args.ids:
        pedidos = {item.strip() for item in args.ids.split(",")}
        casos = [caso for caso in casos if caso["id"] in pedidos]

    resultados = []
    for caso in casos:
        token = abrir_sessao(args.base_url)
        acumulado = {"texto": "", "tools": [], "guard": None, "request_id": None}
        try:
            for mensagem in caso["mensagens"]:
                turno = falar(args.base_url, token, mensagem)
                acumulado["texto"] += "\n" + turno["texto"]
                acumulado["tools"] += turno["tools"]
                acumulado["guard"] = turno["guard"] or acumulado["guard"]
                acumulado["request_id"] = turno["request_id"]
            falhas = avaliar(caso, acumulado)
        except urllib.error.HTTPError as exc:
            falhas = [f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:120]}"]
        except Exception as exc:  # noqa: BLE001 â€” avaliacao precisa reportar, nao quebrar
            falhas = [f"erro: {exc}"]

        resultados.append(
            {
                "id": caso["id"],
                "passou": not falhas,
                "falhas": falhas,
                "tools": acumulado["tools"],
                "guard": acumulado["guard"],
                "texto": acumulado["texto"].strip(),
            }
        )

    aprovados = sum(1 for item in resultados if item["passou"])
    if args.json:
        resumo = {"total": len(resultados), "aprovados": aprovados, "casos": resultados}
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    else:
        for item in resultados:
            marca = "PASS" if item["passou"] else "FAIL"
            detalhe = "" if item["passou"] else " Â· " + "; ".join(item["falhas"])
            print(f"[{marca}] {item['id']:<24} tools={','.join(item['tools']) or '-':<40}{detalhe}")
        print(f"\n{aprovados}/{len(resultados)} aprovados")

    return 0 if aprovados == len(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
