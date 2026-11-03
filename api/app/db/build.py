from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import DataSourceError

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_HEADING = re.compile(r"^##\s+(\d+(?:\.\d+)*)\s+(.*)$", re.MULTILINE)
_NON_DIGIT = re.compile(r"\D")


@dataclass(frozen=True)
class PolicyChunk:
    secao: str
    secao_pai: str
    titulo: str
    text: str
    pagina: int | None
    versao: str | None
    atualizado_em: str | None
    fonte: str | None


def _csv_path(data_dir: Path, table: str) -> Path:
    matches = sorted(data_dir.glob(f"* - {table}.csv"))
    if len(matches) != 1:
        raise DataSourceError(
            f"esperava 1 CSV de '{table}' em {data_dir}, achei {len(matches)}"
        )
    return matches[0]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _phone_digits(value: str) -> str:
    return _NON_DIGIT.sub("", value or "")


def _split_front_matter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(raw)
    if not match:
        return {}, raw
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta, raw[match.end() :]


def _split_blocks(body: str) -> list[tuple[str, str, str]]:
    """Divide o corpo em (secao, titulo, texto). Sem '##', o corpo inteiro e um bloco."""
    headings = list(_HEADING.finditer(body))
    if not headings:
        return [("", "", body.strip())]

    blocks: list[tuple[str, str, str]] = []
    lead = body[: headings[0].start()].strip()
    if lead:
        blocks.append(("", "", lead))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        text = body[heading.end() : end].strip()
        blocks.append((heading.group(1), heading.group(2).strip(), text))
    return blocks


def parse_policy_file(path: Path) -> list[PolicyChunk]:
    meta, body = _split_front_matter(path.read_text(encoding="utf-8"))
    secao_pai = meta.get("secao", "")
    pagina = int(meta["pagina"]) if meta.get("pagina", "").isdigit() else None

    chunks: list[PolicyChunk] = []
    for secao, titulo, text in _split_blocks(body):
        if not text:
            continue
        chunks.append(
            PolicyChunk(
                secao=secao or secao_pai,
                secao_pai=secao_pai,
                titulo=titulo or meta.get("titulo", ""),
                text=text,
                pagina=pagina,
                versao=_text(meta.get("versao")),
                atualizado_em=_text(meta.get("atualizado_em")),
                fonte=_text(meta.get("fonte")),
            )
        )
    return chunks


def load_policies(policies_dir: Path) -> list[PolicyChunk]:
    files = sorted(policies_dir.glob("*.md"))
    if not files:
        raise DataSourceError(f"nenhuma politica encontrada em {policies_dir}")
    chunks: list[PolicyChunk] = []
    for path in files:
        chunks.extend(parse_policy_file(path))
    return chunks


def _insert_categories(conn: sqlite3.Connection, data_dir: Path) -> int:
    rows = _rows(_csv_path(data_dir, "categories"))
    conn.executemany(
        "INSERT INTO categories (category_id, name, description) VALUES (?, ?, ?)",
        [(int(r["category_id"]), r["name"], _text(r["description"])) for r in rows],
    )
    return len(rows)


def _insert_products(conn: sqlite3.Connection, data_dir: Path) -> int:
    rows = _rows(_csv_path(data_dir, "products"))
    payload = []
    for row in rows:
        try:
            specs = json.loads(row["specs"])
        except json.JSONDecodeError as exc:  # dado sujo deve falhar alto, nao passar silencioso
            raise DataSourceError(
                f"specs invalido no produto {row['product_id']}: {exc}"
            ) from exc
        payload.append(
            (
                int(row["product_id"]),
                row["name"],
                int(row["category_id"]),
                float(row["price_brl"]),
                int(row["stock_quantity"]),
                row["status"],
                _text(row["description"]),
                json.dumps(specs, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                _text(row["created_at"]),
            )
        )
    conn.executemany(
        "INSERT INTO products (product_id, name, category_id, price_brl, stock_quantity, status,"
        " description, specs_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        payload,
    )
    return len(payload)


def _insert_customers(conn: sqlite3.Connection, data_dir: Path) -> int:
    rows = _rows(_csv_path(data_dir, "customers"))
    payload = [
        (
            int(r["customer_id"]),
            r["name"],
            r["phone"],
            _phone_digits(r["phone"]),
            _text(r["email"]),
            _text(r["city"]),
        )
        for r in rows
    ]
    conn.executemany(
        "INSERT INTO customers (customer_id, name, phone, phone_digits, email, city)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        payload,
    )
    return len(payload)


def _insert_orders(conn: sqlite3.Connection, data_dir: Path) -> int:
    rows = _rows(_csv_path(data_dir, "orders"))
    payload = [
        (
            int(r["order_id"]),
            int(r["customer_id"]),
            r["order_date"],
            r["status"],
            float(r["total_brl"]),
            _text(r["payment_method"]),
            _text(r["tracking_code"]),
            _text(r["estimated_delivery"]),
            _text(r["notes"]),
        )
        for r in rows
    ]
    conn.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, total_brl,"
        " payment_method, tracking_code, estimated_delivery, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        payload,
    )
    return len(payload)


def _insert_order_items(conn: sqlite3.Connection, data_dir: Path) -> int:
    rows = _rows(_csv_path(data_dir, "order_items"))
    payload = [(int(r["order_id"]), int(r["product_id"]), int(r["quantity"])) for r in rows]
    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity) VALUES (?, ?, ?)",
        payload,
    )
    return len(payload)


def _insert_promotions(conn: sqlite3.Connection, data_dir: Path) -> int:
    rows = _rows(_csv_path(data_dir, "promotions"))
    payload = [
        (
            int(r["promotion_id"]),
            int(r["product_id"]),
            float(r["discount_percent"]),
            _text(r["description"]),
            int(r["is_active"]),
        )
        for r in rows
    ]
    conn.executemany(
        "INSERT INTO promotions (promotion_id, product_id, discount_percent, description,"
        " is_active) VALUES (?, ?, ?, ?, ?)",
        payload,
    )
    return len(payload)


def _insert_policies(conn: sqlite3.Connection, policies_dir: Path) -> int:
    chunks = load_policies(policies_dir)
    for chunk in chunks:
        cursor = conn.execute(
            "INSERT INTO policies (secao, secao_pai, titulo, texto, pagina, versao,"
            " atualizado_em, fonte) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                chunk.secao,
                chunk.secao_pai,
                chunk.titulo,
                chunk.text,
                chunk.pagina,
                chunk.versao,
                chunk.atualizado_em,
                chunk.fonte,
            ),
        )
        conn.execute(
            "INSERT INTO policies_fts (rowid, secao, titulo, texto) VALUES (?, ?, ?, ?)",
            (cursor.lastrowid, chunk.secao, chunk.titulo, chunk.text),
        )
    return len(chunks)


def data_quality_report(conn: sqlite3.Connection) -> dict[str, list[dict[str, object]]]:
    """Divergencias conhecidas nos dados de origem. Reportadas, nunca corrigidas em silencio."""
    mismatched_totals = [
        {
            "order_id": order_id,
            "total_brl": total,
            "soma_itens": round(items_total, 2),
            "diferenca": round(total - items_total, 2),
        }
        for order_id, total, items_total in conn.execute(
            """
            SELECT o.order_id, o.total_brl,
                   COALESCE(SUM(i.quantity * p.price_brl), 0) AS soma
            FROM orders o
            JOIN order_items i ON i.order_id = o.order_id
            JOIN products p ON p.product_id = i.product_id
            GROUP BY o.order_id
            HAVING ABS(o.total_brl - soma) > 0.01
            ORDER BY o.order_id
            """
        )
    ]
    empty_categories = [
        {"category_id": category_id, "name": name}
        for category_id, name in conn.execute(
            """
            SELECT c.category_id, c.name
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.category_id
            WHERE p.product_id IS NULL
            ORDER BY c.category_id
            """
        )
    ]
    return {"totais_divergentes": mismatched_totals, "categorias_sem_produto": empty_categories}


def build_database(db_path: Path, data_dir: Path, policies_dir: Path) -> dict[str, object]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        counts: dict[str, object] = {
            "categories": _insert_categories(conn, data_dir),
            "products": _insert_products(conn, data_dir),
            "customers": _insert_customers(conn, data_dir),
            "orders": _insert_orders(conn, data_dir),
            "order_items": _insert_order_items(conn, data_dir),
            "promotions": _insert_promotions(conn, data_dir),
            "policies": _insert_policies(conn, policies_dir),
        }
        conn.commit()
        counts["integridade"] = conn.execute("PRAGMA foreign_key_check").fetchall() == []
        counts["qualidade_dados"] = data_quality_report(conn)
        return counts
    finally:
        conn.close()
