"""Modo terminal do agente: valida o comportamento sem depender da API HTTP.

    python -m app.cli                       # conversa livre
    python -m app.cli --once "pergunta"     # um turno e sai
    python -m app.cli --once "pergunta" --json
"""

from __future__ import annotations

import argparse
import json

from app.agent.agent import build_agent, run_turn
from app.agent.prompts import active_prompt_version
from app.agent.session import SessionContext
from app.core.config import get_settings
from app.db.build import build_database
from app.db.connection import connect


def _ensure_database():
    settings = get_settings()
    if not settings.database_path.exists():
        build_database(settings.database_path, settings.data_dir, settings.policies_dir)
    return settings


def _render(result, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {
                "answer": result.answer,
                "guard": result.guard,
                "tools": result.tools_used,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "prompt_version": result.prompt_version,
            },
            ensure_ascii=False,
        )

    lines = [f"assistente> {result.answer}"]
    meta = f"  · tools: {', '.join(result.tools_used) or 'nenhuma'}"
    meta += f" · tokens: {result.tokens_in} in / {result.tokens_out} out"
    meta += f" · prompt v{result.prompt_version}"
    if result.guard:
        meta += f" · GUARD: {result.guard}"
    lines.append(meta)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agente de atendimento da Emporio da Musica")
    parser.add_argument("--once", metavar="PERGUNTA", help="responde uma pergunta e encerra")
    parser.add_argument("--json", action="store_true", help="saida em JSON (uso em avaliacao)")
    args = parser.parse_args(argv)

    settings = _ensure_database()
    conn = connect(settings.database_path)
    session = SessionContext()
    agent = build_agent(session, conn)
    history: list = []

    if args.once:
        print(_render(run_turn(agent, history, args.once), as_json=args.json))
        return 0

    print(f"Emporio da Musica · prompt v{active_prompt_version()} · Ctrl+C ou 'sair' para encerrar")
    while True:
        try:
            line = input("cliente> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if line.strip().lower() in {"sair", "exit", "quit"}:
            break
        if not line.strip():
            continue

        resultado = run_turn(agent, history, line)
        print(_render(resultado, as_json=args.json))
        history.extend(resultado.messages)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
