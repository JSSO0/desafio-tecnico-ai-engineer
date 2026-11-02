from __future__ import annotations

import sqlite3

from langchain_core.tools import BaseTool

from app.agent.session import SessionContext
from app.tools.catalog import make_catalog_tools
from app.tools.orders import make_order_tools
from app.tools.payments import make_payment_tools
from app.tools.policies import make_policy_tools


def build_tools(session: SessionContext, conn: sqlite3.Connection) -> list[BaseTool]:
    """Ferramentas da sessao. O estado do cliente fica na closure, fora do alcance do modelo."""
    return [
        *make_catalog_tools(conn),
        *make_order_tools(conn, session),
        *make_policy_tools(conn),
        *make_payment_tools(),
    ]
