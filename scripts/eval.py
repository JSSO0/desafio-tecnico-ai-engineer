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
from pathlib import Path
from typing import Any

from api_client import open_session, say

REPO_ROOT = Path(__file__).resolve().parents[1]
CASOS_PADRAO = REPO_ROOT / "evals" / "casos.jsonl"


def normalize(text: str) -> str:
    decomposto = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch)).lower()


def _missing(texto: str, esperados: list[str]) -> list[str]:
    return [f"faltou {item!r}" for item in esperados if normalize(item) not in texto]


def _forbidden(texto: str, proibidos: list[str]) -> list[str]:
    return [f"nao podia conter {item!r}" for item in proibidos if normalize(item) in texto]


def _missing_tools(usadas: list[str], esperadas: list[str]) -> list[str]:
    return [f"nao chamou {tool}" for tool in esperadas if tool not in usadas]


def avaliar(caso: dict[str, Any], resultado: dict[str, Any]) -> list[str]:
    """Cada regra e uma funcao pura; sem laco aninhado e sem acessar chave que pode faltar."""
    texto = normalize(resultado.get("texto", ""))
    falhas = [
        *_missing(texto, caso.get("deve_conter", [])),
        *_forbidden(texto, caso.get("nao_deve_conter", [])),
        *_missing_tools(resultado.get("tools", []), caso.get("tools_esperadas", [])),
    ]
    esperado = caso.get("guard_esperado")
    if esperado and resultado.get("guard") != esperado:
        falhas.append(f"guard {resultado.get('guard')!r} != {esperado!r}")
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
        token = open_session(args.base_url)
        acumulado = {"texto": "", "tools": [], "guard": None, "request_id": None}
        try:
            for mensagem in caso["mensagens"]:
                turno = say(args.base_url, token, mensagem)
                acumulado["texto"] += "\n" + turno["texto"]
                acumulado["tools"] += turno["tools"]
                acumulado["guard"] = turno["guard"] or acumulado["guard"]
                acumulado["request_id"] = turno["request_id"]
            falhas = avaliar(caso, acumulado)
        except urllib.error.HTTPError as exc:
            falhas = [f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:120]}"]
        except Exception as exc:  # noqa: BLE001 — avaliacao precisa reportar, nao quebrar
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
            detalhe = "" if item["passou"] else " · " + "; ".join(item["falhas"])
            print(f"[{marca}] {item['id']:<24} tools={','.join(item['tools']) or '-':<40}{detalhe}")
        print(f"\n{aprovados}/{len(resultados)} aprovados")

    return 0 if aprovados == len(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
