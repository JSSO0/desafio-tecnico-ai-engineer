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
DEFAULT_CASES = REPO_ROOT / "evals" / "casos.jsonl"


def normalize(text: str) -> str:
    decomposto = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch)).lower()


def _missing(text: str, esperados: list[str]) -> list[str]:
    return [f"faltou {item!r}" for item in esperados if normalize(item) not in text]


def _forbidden(text: str, proibidos: list[str]) -> list[str]:
    return [f"nao podia conter {item!r}" for item in proibidos if normalize(item) in text]


def _missing_tools(usadas: list[str], esperadas: list[str]) -> list[str]:
    return [f"nao chamou {tool}" for tool in esperadas if tool not in usadas]


def evaluate(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    """Cada regra e uma funcao pura; sem laco aninhado e sem acessar chave que pode faltar."""
    text = normalize(result.get("texto", ""))
    failures = [
        *_missing(text, case.get("deve_conter", [])),
        *_forbidden(text, case.get("nao_deve_conter", [])),
        *_missing_tools(result.get("tools", []), case.get("tools_esperadas", [])),
    ]
    esperado = case.get("guard_esperado")
    if esperado and result.get("guard") != esperado:
        failures.append(f"guard {result.get('guard')!r} != {esperado!r}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avalia o agente contra a API em execucao")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--casos", dest="cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--ids", default="", help="lista separada por virgula")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    lines = args.cases.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",")}
        cases = [case for case in cases if case["id"] in wanted]

    results = []
    for case in cases:
        token = open_session(args.base_url)
        accumulated = {"texto": "", "tools": [], "guard": None, "request_id": None}
        try:
            for message in case["mensagens"]:
                turno = say(args.base_url, token, message)
                accumulated["texto"] += "\n" + turno["texto"]
                accumulated["tools"] += turno["tools"]
                accumulated["guard"] = turno["guard"] or accumulated["guard"]
                accumulated["request_id"] = turno["request_id"]
            failures = evaluate(case, accumulated)
        except urllib.error.HTTPError as exc:
            failures = [f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:120]}"]
        except Exception as exc:  # noqa: BLE001 — avaliacao precisa reportar, nao quebrar
            failures = [f"erro: {exc}"]

        results.append(
            {
                "id": case["id"],
                "passou": not failures,
                "falhas": failures,
                "tools": accumulated["tools"],
                "guard": accumulated["guard"],
                "texto": accumulated["texto"].strip(),
            }
        )

    passed = sum(1 for item in results if item["passou"])
    if args.json:
        resumo = {"total": len(results), "aprovados": passed, "casos": results}
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    else:
        for item in results:
            mark = "PASS" if item["passou"] else "FAIL"
            detail = "" if item["passou"] else " · " + "; ".join(item["falhas"])
            print(f"[{mark}] {item['id']:<24} tools={','.join(item['tools']) or '-':<40}{detail}")
        print(f"\n{passed}/{len(results)} aprovados")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
