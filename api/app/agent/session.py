from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionContext:
    """Support state the model does not control.

    Customer identity lives here, on the server: tools read from here, never from
    argumento que o modelo inventou. E o que impede IDOR/BOLA via prompt injection.
    """

    customer_id: int | None = None
    customer_name: str | None = None

    @property
    def identified(self) -> bool:
        return self.customer_id is not None
