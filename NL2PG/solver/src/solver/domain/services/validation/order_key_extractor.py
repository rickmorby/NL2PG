"""Estrazione delle chiavi di ordinamento dal risultato gold.

Data la gold query e i nomi delle colonne del risultato, restituisce gli indici
delle colonne che compongono la chiave ORDER BY esterna: sono le chiavi di parita'
(tie) oltre alle quali l'ordine delle righe non e' determinabile.

:author: Riccardo Morabito
"""

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError, TokenError

from solver.domain.services.validation.order_sensitivity_policy import query_has_outer_order_by


def extract_order_key_indexes(query: str, gold_columns: list[str]) -> list[int]:
    """Restituisce gli indici (nel risultato gold) delle colonne della chiave ORDER BY.

    Una lista vuota significa: nessun ORDER BY esterno riconosciuto oppure chiavi
    non riconducibili alle colonne proiettate (il chiamante trattera' il confronto
    come strettamente posizionale).
    """
    if not query_has_outer_order_by(query) or not gold_columns:
        return []

    try:
        tree = parse_one(query, read="postgres")
    except (ParseError, TokenError, ValueError, AttributeError):
        return []

    select_node = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    order_node = None if select_node is None else select_node.args.get("order")
    if order_node is None:
        return []

    lowered = [col.strip().lower() for col in gold_columns]
    indexes: list[int] = []
    for key in order_node.expressions:
        idx = _resolve_key_index(key, select_node, lowered)
        if idx is not None and idx not in indexes:
            indexes.append(idx)
    return indexes


def _resolve_key_index(
    key: exp.Expression,
    select_node: exp.Select,
    lowered: list[str],
) -> int | None:
    """Risolve una singola espressione ORDER BY nell'indice di colonna proiettata."""
    if isinstance(key, exp.Ordered):
        key = key.this
    if isinstance(key, exp.Literal) and key.is_int:
        position = int(key.this)
        return position - 1 if 1 <= position <= len(lowered) else None
    name = _key_name(key)
    if name and name in lowered:
        return lowered.index(name)
    return _projection_match(key, select_node, lowered)


def _key_name(key: exp.Expression) -> str:
    """Nome della chiave ORDER BY per colonne e alias."""
    if isinstance(key, exp.Column):
        return key.name.lower()
    if isinstance(key, exp.Alias):
        return key.alias.lower()
    return ""


def _projection_match(
    key: exp.Expression, select_node: exp.Select | None, lowered: list[str]
) -> int | None:
    """Cerca il testo della chiave tra le proiezioni (espressioni complesse)."""
    if select_node is None:
        return None
    key_sql = key.sql(dialect="postgres").lower()
    for position, projection in enumerate(select_node.selects):
        if position < len(lowered) and projection.sql(dialect="postgres").lower() == key_sql:
            return position
    return None
