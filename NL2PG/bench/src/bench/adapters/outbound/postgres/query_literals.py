"""Analisi dei literal di filtro nelle query SQL per il mutation testing.

Estrae le coppie colonna/valore usate nel WHERE (uguaglianze e IN) e riconosce
le aggregazioni scalari: sono i bersagli che rendono una mutazione sensibile.

:author: Riccardo Morabito
"""

from collections import defaultdict
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError


def get_filter_literals(query: str, table_name: str) -> dict[str, list[Any]]:
    """Estrae i valori letterali confrontati con le colonne della tabella nel WHERE."""
    try:
        tree = parse_one(query, read="postgres")
    except (ParseError, ValueError):
        return {}
    aliases = {table_name.lower()}
    for t in tree.find_all(exp.Table):
        if t.name.lower() == table_name.lower() and t.alias:
            aliases.add(t.alias.lower())
    literals: dict[str, list[Any]] = defaultdict(list)
    for comparison in tree.find_all(exp.EQ):
        _collect_eq_literals(comparison, aliases, literals)
    for in_expr in tree.find_all(exp.In):
        _collect_in_literals(in_expr, aliases, literals)
    return dict(literals)


def is_scalar_aggregate(query: str) -> bool:
    """Verifica se la query e' un'aggregazione scalare (senza GROUP BY)."""
    try:
        tree = parse_one(query, read="postgres")
        return bool(tree.find(exp.AggFunc)) and tree.args.get("group") is None
    except (ParseError, ValueError, AttributeError):
        return False


def _collect_eq_literals(
    comparison: exp.EQ, aliases: set[str], literals: dict[str, list[Any]]
) -> None:
    """Raccoglie i valori da un confronto di uguaglianza colonna = letterale."""
    left, right = comparison.this, comparison.expression
    column, value = _column_literal_pair(left, right) or (None, None)
    if column is None:
        return
    if column.table and column.table.lower() not in aliases:
        return
    parsed = _literal_value(value)
    if parsed is not None:
        literals[column.name.lower()].append(parsed)


def _collect_in_literals(
    in_expr: exp.In, aliases: set[str], literals: dict[str, list[Any]]
) -> None:
    """Raccoglie i valori da una condizione colonna IN (letterali)."""
    column = in_expr.this
    if not isinstance(column, exp.Column):
        return
    if column.table and column.table.lower() not in aliases:
        return
    for item in in_expr.expressions:
        parsed = _literal_value(item)
        if parsed is not None:
            literals[column.name.lower()].append(parsed)


def _column_literal_pair(
    left: exp.Expression, right: exp.Expression
) -> tuple[exp.Column, exp.Expression] | None:
    """Restituisce la coppia (colonna, letterale) in qualunque ordine."""
    if isinstance(left, exp.Column) and isinstance(right, (exp.Literal, exp.Boolean)):
        return left, right
    if isinstance(right, exp.Column) and isinstance(left, (exp.Literal, exp.Boolean)):
        return right, left
    return None


def _literal_value(node: exp.Expression) -> Any:
    """Converte un nodo letterale sqlglot nel valore Python corrispondente."""
    if isinstance(node, exp.Boolean):
        return bool(node.this)
    if isinstance(node, exp.Literal) and node.is_string:
        return node.name
    if isinstance(node, exp.Literal):
        try:
            return node.to_py()
        except ValueError:
            return None
    return None
