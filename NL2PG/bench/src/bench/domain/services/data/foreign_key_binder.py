"""Binding delle chiavi esterne a PK reali e ordinamento topologico delle tabelle.

``ForeignKeyBinder`` lega ogni colonna FK a una PK reale gia' generata del
padre (passata finale, indipendente dall'ordine di generazione) e mantiene
uniche le PK composite dopo il binding; ``table_order`` fornisce l'ordine
topologico (padri prima dei figli) per la costruzione dello script INSERT.

:author: Riccardo Morabito
"""

from random import Random
from typing import Any

from bench.domain.models.data import SchemaModel

_COMPOSITE_PK_MIN = 2
_MAX_DEDUPE_ATTEMPTS = 50


def table_order(schema: SchemaModel) -> list[str]:
    """Ordine topologico delle tabelle: i padri prima dei figli (Kahn)."""
    edges: dict[str, list[str]] = {name: [] for name in schema.tables}
    indegree: dict[str, int] = {name: 0 for name in schema.tables}
    for name, table in schema.tables.items():
        for column in table.fk_columns:
            parent = column.fk_parent_table
            if parent and parent != name and parent in schema.tables:
                edges[parent].append(name)
                indegree[name] += 1
    queue = [name for name in schema.tables if indegree[name] == 0]
    order: list[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for dependent in edges[current]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    for name in schema.tables:
        if name not in order:
            order.append(name)
    return order


class ForeignKeyBinder:
    """Lega le FK a PK reali del padre e mantiene uniche le PK composite."""

    def __init__(self, null_rate: float = 0.05) -> None:
        """Inietta il tasso di NULL applicabile alle FK nullable."""
        self._null_rate = null_rate

    def bind(self, schema: SchemaModel, rows: dict[str, list[dict[str, Any]]], rng: Random) -> None:
        """Sostituisce ogni FK con una PK reale del padre (o NULL se nullable)."""
        for table_name in rows:
            table = schema.table(table_name)
            exclusive_bound = self._bind_exclusive_arcs(table, rows, rng)
            for column in table.fk_columns:
                if exclusive_bound and column.nullable and column.fk_parent_table != table.name:
                    continue
                self._bind_column(table, column, rows, rng)

    def _bind_exclusive_arcs(
        self, table: Any, rows: dict[str, list[dict[str, Any]]], rng: Random
    ) -> bool:
        """Popola esattamente una FK per riga nelle tabelle con archi esclusivi."""
        exclusive_fks = [
            c for c in table.fk_columns if c.nullable and c.fk_parent_table != table.name
        ]
        if len(exclusive_fks) < _COMPOSITE_PK_MIN:
            return False
        has_exclusive = any(
            "IS NULL" in str(getattr(c, "check_expr", "")).upper()
            or "<>" in str(getattr(c, "check_expr", ""))
            or "= 1" in str(getattr(c, "check_expr", ""))
            for c in table.columns
        )
        if not has_exclusive:
            return False
        for row in rows[table.name]:
            chosen_col = rng.choice(exclusive_fks)
            for col in exclusive_fks:
                if col.name == chosen_col.name:
                    parent = rows.get((col.fk_parent_table or "").lower(), [])
                    parent_keys = [
                        r[col.fk_parent_column or ""]
                        for r in parent
                        if r.get(col.fk_parent_column or "") is not None
                    ]
                    row[col.name] = rng.choice(parent_keys) if parent_keys else None
                else:
                    row[col.name] = None
        return True

    def _bind_column(
        self,
        table,
        column,
        rows: dict[str, list[dict[str, Any]]],
        rng: Random,
    ) -> None:
        """Lega una singola colonna FK, gestendo self-reference, PK e UNIQUE."""
        parent = rows.get((column.fk_parent_table or "").lower(), [])
        parent_keys = [
            row[column.fk_parent_column or ""]
            for row in parent
            if row.get(column.fk_parent_column or "") is not None
        ]
        is_self = column.fk_parent_table == table.name
        is_single_pk = len(table.pk_columns) == 1 and column.name in table.pk_columns
        must_be_unique = column.is_unique or is_single_pk

        if must_be_unique and len(rows[table.name]) > len(parent_keys):
            rows[table.name] = rows[table.name][: len(parent_keys)]

        used_unique: set[Any] = set()
        available_unique = list(parent_keys)
        if must_be_unique and available_unique:
            rng.shuffle(available_unique)
        bound_prefix: list[Any] = []

        for row in rows[table.name]:
            if column.nullable and rng.random() < self._null_rate:
                row[column.name] = None
            elif is_self:
                if bound_prefix:
                    row[column.name] = rng.choice(bound_prefix)
            elif parent_keys:
                row[column.name] = self._pick_parent_key(
                    parent_keys, available_unique, used_unique, must_be_unique, rng
                )
            if is_self and row.get(column.fk_parent_column or "") is not None:
                bound_prefix.append(row[column.fk_parent_column or ""])

    @staticmethod
    def _pick_parent_key(
        parent_keys: list[Any],
        available_unique: list[Any],
        used_unique: set[Any],
        must_be_unique: bool,
        rng: Random,
    ) -> Any:
        """Seleziona una chiave genitore gestendo l'unicità senza ripetizioni."""
        if must_be_unique and available_unique:
            val = available_unique.pop()
            used_unique.add(val)
            return val
        if must_be_unique and used_unique:
            remaining = [k for k in parent_keys if k not in used_unique]
            if remaining:
                val = rng.choice(remaining)
                used_unique.add(val)
                return val
        return rng.choice(parent_keys)

    def dedupe_composite_keys(
        self, schema: SchemaModel, rows: dict[str, list[dict[str, Any]]], rng: Random
    ) -> None:
        """Rende uniche le PK composite dopo il binding FK (che puo' creare collisioni)."""
        for table_name, table_rows in rows.items():
            table = schema.table(table_name)
            if len(table.pk_columns) < _COMPOSITE_PK_MIN:
                continue
            pk_fk_columns = [c for c in table.fk_columns if c.name in table.pk_columns]
            seen: set[tuple] = set()
            for row in table_rows:
                key = tuple(row[c] for c in table.pk_columns)
                attempts = 0
                while key in seen and attempts < _MAX_DEDUPE_ATTEMPTS:
                    column = pk_fk_columns[attempts % len(pk_fk_columns)]
                    parent = rows.get((column.fk_parent_table or "").lower(), [])
                    parent_keys = [
                        r[column.fk_parent_column or ""]
                        for r in parent
                        if r.get(column.fk_parent_column or "") is not None
                    ]
                    candidates = [k for k in parent_keys if k != row[column.name]]
                    if not candidates:
                        break
                    row[column.name] = rng.choice(candidates)
                    key = tuple(row[c] for c in table.pk_columns)
                    attempts += 1
                seen.add(key)
