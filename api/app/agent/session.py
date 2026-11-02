from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionContext:
    """Estado de atendimento que o modelo nao controla.

    A identidade do cliente fica aqui, no servidor: as ferramentas leem daqui, nunca do
    argumento que o modelo inventou. E o que impede IDOR/BOLA via prompt injection.
    """

    customer_id: int | None = None
    customer_name: str | None = None

    @property
    def identified(self) -> bool:
        return self.customer_id is not None
