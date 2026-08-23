"""Policy di naming degli identificatori dello schema (servizio di dominio puro).

Il benchmark esige identificatori in lingua italiana (tabelle, colonne, alias) per
coerenza con le question in italiano. Questa policy rileva i termini inglesi comuni
usati come identificatori nel DDL, con una whitelist di eccezioni ammesse dal gergo
tecnico italiano.

:author: Riccardo Morabito
"""

from re import compile as re_compile
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

_ENGLISH_TERMS: frozenset[str] = frozenset(
    {
        "customer",
        "product",
        "price",
        "quantity",
        "name",
        "address",
        "phone",
        "city",
        "country",
        "total",
        "amount",
        "status",
        "category",
        "supplier",
        "invoice",
        "payment",
        "shipping",
        "warehouse",
        "stock",
        "employee",
        "department",
        "salary",
        "company",
        "user",
        "account",
        "item",
        "purchase",
        "discount",
        "brand",
        "lifecycle",
        "dept",
        "proj",
        "cd",
        "code",
    }
)

_WHITELIST: frozenset[str] = frozenset({"email"})

_RE_IDENTIFIER = re_compile(r"^[a-z_][a-z0-9_]*$")


def _token_is_english(identifier: str) -> bool:
    """Verifica se qualche segmento snake_case dell'identificatore è un termine inglese."""
    ident = identifier.lower()
    if ident in _WHITELIST:
        return False
    return any(part in _ENGLISH_TERMS for part in ident.split("_"))


def _collect_hits(tree: exp.Expression, hits: set[tuple[str, str]]) -> None:
    """Raccoglie tabelle e colonne non conformi da un albero sintattico."""
    for create in tree.find_all(exp.Create):
        if not isinstance(create.this, exp.Schema):
            continue
        table_name = create.this.this.name if create.this.this else ""
        table_ok = bool(table_name) and _RE_IDENTIFIER.fullmatch(table_name) is not None
        if table_ok and _token_is_english(table_name):
            hits.add(("tabella", table_name))
        for cd in create.find_all(exp.ColumnDef):
            col_name = cd.name
            if not col_name or _RE_IDENTIFIER.fullmatch(col_name) is None:
                continue
            if _token_is_english(col_name):
                hits.add(("colonna", f"{table_name}.{col_name}"))


def find_english_identifiers(ddl: str) -> list[tuple[str, str]]:
    """Estrae tabelle e colonne con termini inglesi dal DDL.

    Restituisce una lista di coppie ``(tipo, identificatore)`` dove ``tipo`` è
    'tabella' o 'colonna'. Ordinata per tipo e nome per determinismo.
    """
    try:
        tree = parse_one(ddl, read="postgres")
        trees = [tree]
    except ParseError:
        trees = []
        for stmt_ddl in _split_statements(ddl):
            try:
                trees.append(parse_one(stmt_ddl, read="postgres"))
            except ParseError:
                continue

    hits: set[tuple[str, str]] = set()
    for tree in trees:
        _collect_hits(tree, hits)
    return sorted(hits)


def english_identifier_error(hits: list[tuple[str, str]]) -> str | None:
    """Costruisce il messaggio di errore per gli identificatori non conformi."""
    if not hits:
        return None
    details = ", ".join(f"{kind} '{name}'" for kind, name in hits)
    return (
        "Il DDL contiene identificatori in inglese, ma la policy del progetto richiede "
        f"identificatori in italiano: {details}. Rinominali usando termini italiani "
        "(es. category_name -> nome_categoria), mantenendo coerenza tra DDL, dati e query."
    )


def _split_statements(ddl: str) -> list[str]:
    """Suddivide lo script su punti e virgola fuori da letterali stringa."""
    parts: list[str] = []
    buf: list[str] = []
    in_str = False
    for ch in ddl:
        if ch == "'":
            in_str = not in_str
        if ch == ";" and not in_str:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [p.strip() for p in parts if p.strip()]
