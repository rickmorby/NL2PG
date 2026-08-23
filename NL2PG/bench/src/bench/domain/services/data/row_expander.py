"""Espansione dei template canonici in righe per tabella.

Orchestra la generazione dei volumi calcolati da ``RowCounter``: distribuzione
dei template, delega della riga singola al ``RowBuilder`` e risoluzione delle
collisioni su PK composite e gruppi UNIQUE compositi.

:author: Riccardo Morabito
"""

from random import Random
from typing import Any

from bench.domain.models.data import (
    DataSpecDTO,
    SchemaModel,
    TableDataSpecDTO,
    TableSchema,
)
from bench.domain.services.data.check_constraints import satisfies_check
from bench.domain.services.data.column_types import is_date_type, is_integer_type, shift_value
from bench.domain.services.data.row_builder import RowBuilder
from bench.domain.services.data.unique_values import _MAX_SUFFIX_ATTEMPTS, _unique_string


class RowExpander:
    """Espande i template canonici in righe per tabella (loop e PK composite)."""

    def __init__(
        self, null_rate: float = 0.05, dup_rate: float = 0.03, outlier_rate: float = 0.02
    ) -> None:
        """Inietta i tassi di rumore e delega la riga singola al RowBuilder."""
        self._dup_rate = dup_rate
        self._builder = RowBuilder(null_rate, dup_rate, outlier_rate)

    def expand(
        self,
        spec: DataSpecDTO,
        schema: SchemaModel,
        counts: dict[str, int],
        rng: Random,
    ) -> dict[str, list[dict[str, Any]]]:
        """Genera le righe di ogni tabella espandendo i template lungo gli assi."""
        rows: dict[str, list[dict[str, Any]]] = {}
        for table_spec in spec.tables:
            table = schema.table(table_spec.table)
            count = counts[table.name.lower()]
            rows[table.name.lower()] = self._expand_table(table_spec, table, count, rng)
        return rows

    def _expand_table(
        self,
        table_spec: TableDataSpecDTO,
        table: TableSchema,
        count: int,
        rng: Random,
    ) -> list[dict[str, Any]]:
        """Genera le righe di una singola tabella da template, variazioni e rumore."""
        result: list[dict[str, Any]] = []
        templates = table_spec.templates
        base = count // len(templates)
        remainder = count % len(templates)
        used_pk: dict[str, set[Any]] = {col: set() for col in table.pk_columns}
        used_unique: dict[str, set[Any]] = {
            col.name: set()
            for col in table.columns
            if col.is_unique and not col.is_pk and not col.is_fk
        }
        used_composite: set[tuple] = set()
        used_composite_unique: dict[tuple[str, ...], set[tuple]] = {
            tuple(group): set() for group in table.unique_groups if len(group) > 1
        }
        for template_index, template in enumerate(templates):
            instances = base + (1 if template_index < remainder else 0)
            for instance_index in range(instances):
                duplicate = rng.random() < self._dup_rate and bool(result)
                row = self._builder.build(
                    table_spec,
                    table,
                    template,
                    instance_index,
                    used_pk,
                    used_unique,
                    rng,
                    duplicate,
                )
                if len(table.pk_columns) > 1:
                    self._ensure_composite_unique(table, row, used_composite)
                for group_key, used_set in used_composite_unique.items():
                    self._ensure_composite_unique_group(table, row, list(group_key), used_set)
                result.append(row)
        return result

    @staticmethod
    def _ensure_composite_unique(
        table: TableSchema, row: dict[str, Any], used_composite: set[tuple]
    ) -> None:
        """Rende unica la PK composite incrementando l'ultima colonna in caso di collisione."""
        composite_key = tuple(row[col] for col in table.pk_columns)
        suffix = 1
        while composite_key in used_composite:
            pk_col = table.pk_columns[-1]
            if is_integer_type(table.column(pk_col).data_type):
                row[pk_col] = int(row[pk_col]) + suffix
            suffix += 1
            composite_key = tuple(row[col] for col in table.pk_columns)
        used_composite.add(composite_key)

    @staticmethod
    def _ensure_composite_unique_group(
        table: TableSchema,
        row: dict[str, Any],
        group: list[str],
        used: set[tuple],
    ) -> None:
        """Rende unica una combinazione UNIQUE composita."""
        key = tuple(row[col] for col in group)
        suffix = 1
        while True:
            col_schema = table.column(group[-1])
            check = getattr(col_schema, "check_expr", None) if col_schema else None
            val_ok = satisfies_check(str(row[group[-1]]), check) if col_schema else True
            if key not in used and val_ok:
                break
            last_col = group[-1]
            if col_schema and is_integer_type(col_schema.data_type):
                row[last_col] = int(row[last_col]) + suffix
            elif col_schema and is_date_type(col_schema.data_type):
                row[last_col] = shift_value(row[last_col], col_schema, suffix)
            else:
                val = str(row[last_col])
                row[last_col] = _unique_string(
                    val, suffix, col_schema.max_length if col_schema else None, check
                )
            suffix += 1
            key = tuple(row[col] for col in group)
            if suffix > _MAX_SUFFIX_ATTEMPTS:
                break
        used.add(key)
