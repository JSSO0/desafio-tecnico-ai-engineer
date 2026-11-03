from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).with_name("prompts")


def prompt_version(text: str) -> str:
    """Short prompt hash: goes to the audit log, so we know which prompt answered what."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


@lru_cache
def load_prompt(name: str = "v1") -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt nao encontrado: {path}")
    return path.read_text(encoding="utf-8").strip()


def active_prompt_version() -> str:
    return prompt_version(load_prompt())


def system_prompt_for(customer_name: str | None = None) -> str:
    """Base prompt + session state.

    Without this the model does not know the customer is already identified (history keeps the
    conversation, not tool results) and asks for the phone again on the next turn.
    """
    base = load_prompt()
    if not customer_name:
        return base
    primeiro_nome = customer_name.split()[0]
    return (
        base
        + "\n\n# Estado desta sessão\n"
        + f"O cliente já foi identificado nesta conversa: {primeiro_nome}. "
        + "Não peça o telefone de novo; consulte os pedidos direto.\n"
    )
