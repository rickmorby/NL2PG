"""Costruzione dello script INSERT a batch con ordinamento topologico.

``InsertScriptBuilder`` genera lo script multi-riga per ogni tabella (padri
prima dei figli) con formattazione SQL robusta di NULL, booleani, numeri,
date e stringhe.

:author: Riccardo Morabito
"""

from typing import Any

from bench.domain.models.data import ColumnSchema, SchemaModel
from bench.domain.services.data.column_types import (
    is_bool_type,
    is_integer_type,
    is_numeric_type,
    round_numeric,
)
from bench.domain.services.data.foreign_key_binder import table_order


class InsertScriptBuilder:
    """Costruisce lo script INSERT multi-riga per tabella, padri prima dei figli."""

    def __init__(self, batch_size: int = 100) -> None:
        """Inietta la dimensione del batch INSERT (sezione [data])."""
        self._batch_size = batch_size

    def build(self, schema: SchemaModel, rows: dict[str, list[dict[str, Any]]]) -> str:
        """Costruisce lo script completo a partire dalle righe generate."""
        statements: list[str] = []
        for table_name in table_order(schema):
            table_rows = rows.get(table_name, [])
            table = schema.table(table_name)
            columns = [c for c in table.columns if not c.is_generated]
            if not columns:
                continue
            names = ", ".join(f'"{c.name}"' for c in columns)
            for start in range(0, len(table_rows), self._batch_size):
                batch = table_rows[start : start + self._batch_size]
                values = ", ".join(
                    "(" + ", ".join(self._format_value(row.get(c.name), c) for c in columns) + ")"
                    for row in batch
                )
                statements.append(f'INSERT INTO "{table.name}" ({names}) VALUES\n{values};')
        return "\n\n".join(statements)

    @staticmethod
    def _format_value(value: Any, column: ColumnSchema) -> str:
        """Formatta un valore SQL: stringhe quotate, NULL, booleani, numeri, date."""
        if value is None:
            return "NULL"
        if (
            isinstance(value, str)
            and column.max_length is not None
            and len(value) > column.max_length
        ):
            value = value[: column.max_length]
        if is_bool_type(column.data_type):
            return "TRUE" if value else "FALSE"
        if is_integer_type(column.data_type):
            return str(int(value))
        if is_numeric_type(column.data_type):
            return str(round_numeric(value, column))
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        return str(value)
