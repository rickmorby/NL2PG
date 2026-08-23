"""Policy sui tipi delle colonne monetarie (servizio di dominio puro).

Gli importi espressi come TEXT costringono il solver a cast impliciti non dichiarati
nelle question e indeboliscono i vincoli del dato: la policy li rileva dal DDL
incrociando il nome colonna con il lessico economico italiano.

:author: Riccardo Morabito
"""

import re
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

_MONEY_TOKEN = re.compile(
    r"\b(importo|prezzo|totale|saldo|costo|stipendio|canone|premio|fatturato"
    r"|valore|ricavo|emolumento)\w*",
    re.IGNORECASE,
)

_RE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _is_moneyish(column_name: str) -> bool:
    """Verifica se il nome colonna appartiene al lessico economico."""
    return bool(_MONEY_TOKEN.search(column_name))


def _collect_from_ast(tree: exp.Expression, hits: set[tuple[str, str]]) -> None:
    """Raccoglie le colonne monetarie TEXT da un albero sintattico valido."""
    for create in tree.find_all(exp.Create):
        if not isinstance(create.this, exp.Schema):
            continue
        table_name = create.this.this.name if create.this.this else ""
        for cd in create.find_all(exp.ColumnDef):
            col_name = cd.name
            dtype = cd.args.get("kind")
            type_sql = str(getattr(dtype, "this", "") or "")
            if not col_name or not _RE_IDENTIFIER.fullmatch(col_name.lower()):
                continue
            if "text" in type_sql.lower() and _is_moneyish(col_name.lower()):
                hits.add((table_name, col_name))


def _split_statements(ddl: str) -> list[str]:
    buf: list[str] = []
    stmts: list[str] = []
    in_str = False
    for ch in ddl:
        if ch == "'":
            in_str = not in_str
        if ch == ";" and not in_str:
            stmts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return [s.strip() for s in stmts if s.strip()]


def _collect_fallback(ddl: str, hits: set[tuple[str, str]]) -> None:
    """Fallback statement-per-statement per DDL con costrutti non supportati."""
    for stmt_ddl in _split_statements(ddl):
        m = re.match(r"CREATE\s+TABLE\s+(\w+)\s*\(", stmt_ddl, re.I)
        if not m:
            continue
        table_name = m.group(1).lower()
        body = stmt_ddl[m.end() : stmt_ddl.rfind(")")]
        for part in _split_top_level(body):
            cm = re.match(r'"?(\w+)"?\s+TEXT\b', part.strip(), re.I)
            if (
                cm
                and _RE_IDENTIFIER.fullmatch(cm.group(1).lower())
                and _is_moneyish(cm.group(1).lower())
            ):
                hits.add((table_name, cm.group(1)))


def find_text_monetary_columns(ddl: str) -> list[tuple[str, str]]:
    """Ritorna le coppie ``(tabella, colonna)`` monetarie dichiarate TEXT."""
    hits: set[tuple[str, str]] = set()
    try:
        _collect_from_ast(parse_one(ddl, read="postgres"), hits)
        return sorted(hits)
    except ParseError:
        pass
    _collect_fallback(ddl, hits)
    return sorted(hits)


def text_monetary_error(hits: list[tuple[str, str]]) -> str | None:
    """Costruisce il messaggio d'errore per le colonne monetarie testuali."""
    if not hits:
        return None
    details = ", ".join(f"{t}.{c}" for t, c in hits)
    return (
        "Colonne monetarie dichiarate TEXT: " + details + ". "
        "Usa NUMERIC(12,2) per gli importi: il tipo testo impone cast impliciti al "
        "solver e indebolisce i vincoli del dato."
    )


def _split_top_level(body: str) -> list[str]:
    parts, buf, depth, in_str = [], [], 0, False
    for ch in body:
        if ch == "'":
            in_str = not in_str
        if not in_str:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(buf))
                buf = []
                continue
        buf.append(ch)
    last = "".join(buf).strip()
    if last:
        parts.append(last)
    return [p.strip() for p in parts if p.strip()]
