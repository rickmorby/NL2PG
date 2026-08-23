"""Tiebreaker automatico dell'ORDER BY per gold query riproducibili.

Garantisce che l'ultimo criterio di ordinamento sia una colonna univoca
(PK o UNIQUE): in assenza di univocita' il gold result non e' deterministico
anche a parita' di ORDER BY dichiarato.

:author: Riccardo Morabito
"""

from typing import Any

from sqlglot import exp

from bench.domain.exceptions import DatabaseClientError
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from psycopg.errors import Error as PgError


def ensure_tiebreaker(
    query: Any, tree: exp.Expression, schema: str, sandbox: SandboxPort
) -> None:
    """Aggiunge un tiebreaker univoco (GROUP BY o colonna unica ASC) se necessario."""
    order = tree.args.get("order")
    if not order or not order.expressions:
        return
    last_expr = order.expressions[-1]
    last = last_expr.this if isinstance(last_expr, exp.Ordered) else last_expr
    col = last.find(exp.Column) if last is not None else None
    try:
        model = sandbox.introspect_schema(schema)
    except (DatabaseClientError, PgError, KeyError, AttributeError, ValueError):
        return
    unique_cols = collect_unique_columns(model)
    target_col = resolve_column_alias(tree, col.name.lower()) if col else ""
    if target_col in unique_cols:
        return

    group = tree.args.get("group")
    if group and group.expressions and not tree.find(exp.GroupingSets):
        for g_expr in group.expressions:
            if not any(
                e.this.sql(dialect="postgres") == g_expr.sql(dialect="postgres")
                for e in order.expressions
            ):
                order.expressions.append(exp.Ordered(this=g_expr.copy()))
        query.query = tree.sql(dialect="postgres")
        return

    hint = sorted(unique_cols)[0] if unique_cols else "id"
    order.expressions.append(exp.Ordered(this=exp.Column(this=exp.to_identifier(hint))))
    query.query = tree.sql(dialect="postgres")


def collect_unique_columns(model: Any) -> set[str]:
    """Estrae l'insieme delle colonne univoche (PK o vincolo UNIQUE) dello schema."""
    unique_cols: set[str] = set()
    for table in model.tables.values():
        if len(table.pk_columns) == 1:
            unique_cols.add(table.pk_columns[0].lower())
        for group in table.unique_groups:
            if len(group) == 1:
                unique_cols.add(group[0].lower())
    return unique_cols


def resolve_column_alias(tree: exp.Expression, col_name: str) -> str:
    """Risolve un eventuale alias di proiezione risalendo alla colonna fisica sottostante."""
    for a in tree.find_all(exp.Alias):
        if a.alias.lower() == col_name:
            col_expr = a.this.find(exp.Column)
            if col_expr:
                return col_expr.name.lower()
    return col_name
