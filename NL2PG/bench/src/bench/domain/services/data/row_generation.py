"""Generazione delle righe per tabella: espansione template e rumore.

Due responsabilita' separate: ``RowExpander`` orchestra l'espansione dei
template canonici per tabella (loop, duplicati, PK composite, UNIQUE),
``RowBuilder`` costruisce una singola riga applicando variazioni, PK e valori
UNIQUE univoci e rumore controllato (NULL, outlier). I volumi sono calcolati
da ``RowCounter``.

:author: Riccardo Morabito
"""

import random
from typing import Any

from bench.domain.models.data import (
    ColumnSchema,
    ColumnVariationDTO,
    DataSpecDTO,
    SchemaModel,
    TableDataSpecDTO,
    TableSchema,
)
from bench.domain.services.data.column_types import (
    is_integer_type,
    neutral_value,
    scale_value,
    shift_value,
)

_OUTLIER_COIN_FLIP = 0.5


def _generate_unique(
    column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
) -> Any:
    """Genera un valore univoco partendo dal template (sequenziale per int, suffisso per str)."""
    if is_integer_type(column.data_type):
        base = template_value if isinstance(template_value, int) else 1
        candidate = base + instance_index
        while candidate in used:
            candidate += 1
    else:
        base = template_value if template_value is not None else column.name
        candidate = base if instance_index == 0 else f"{base}_{instance_index}"
        while candidate in used:
            candidate = f"{candidate}_"
    used.add(candidate)
    return candidate


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
        rng: random.Random,
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
        rng: random.Random,
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
        """Rende unica una combinazione UNIQUE composita incrementando l'ultima colonna."""
        key = tuple(row[col] for col in group)
        suffix = 1
        while key in used:
            last_col = group[-1]
            col_schema = table.column(last_col)
            if col_schema and is_integer_type(col_schema.data_type):
                row[last_col] = int(row[last_col]) + suffix
            else:
                row[last_col] = f"{row[last_col]}_{suffix}"
            suffix += 1
            key = tuple(row[col] for col in group)
        used.add(key)


class RowBuilder:
    """Costruisce una singola riga: PK e UNIQUE univoche, variazioni e rumore controllato."""

    def __init__(
        self, null_rate: float = 0.05, dup_rate: float = 0.03, outlier_rate: float = 0.02
    ) -> None:
        """Inietta i tassi di rumore applicati alla riga."""
        self.null_rate = null_rate
        self.dup_rate = dup_rate
        self._outlier_rate = outlier_rate

    def build(
        self,
        table_spec: TableDataSpecDTO,
        table: TableSchema,
        template: dict[str, Any],
        instance_index: int,
        used_pk: dict[str, set[Any]],
        used_unique: dict[str, set[Any]],
        rng: random.Random,
        duplicate: bool,
    ) -> dict[str, Any]:
        """Costruisce una riga applicando variazioni, PK/UNIQUE uniche, NULL e outlier."""
        row: dict[str, Any] = {}
        for column in table.columns:
            variation = table_spec.variations.get(column.name)
            template_value = template.get(column.name)
            self._set_column_value(
                column,
                template_value,
                variation,
                instance_index,
                used_pk,
                used_unique,
                rng,
                duplicate,
                row,
            )
            self._inject_noise(column, variation, template_value, row, rng)
        for column in table.columns:
            if row[column.name] is None and not column.nullable and not column.is_pk:
                row[column.name] = neutral_value(column)
        return row

    def _set_column_value(
        self,
        column: ColumnSchema,
        template_value: Any,
        variation: ColumnVariationDTO | None,
        instance_index: int,
        used_pk: dict[str, set[Any]],
        used_unique: dict[str, set[Any]],
        rng: random.Random,
        duplicate: bool,
        row: dict[str, Any],
    ) -> None:
        """Assegna il valore della colonna: PK, UNIQUE, FK/duplicato, variazione o template."""
        if column.is_pk:
            row[column.name] = self._unique_pk_value(
                column, template_value, instance_index, used_pk[column.name]
            )
        elif column.is_unique and not column.is_fk and column.name in used_unique:
            row[column.name] = self._unique_value(
                column, template_value, instance_index, used_unique[column.name]
            )
        elif column.is_fk or duplicate:
            row[column.name] = template_value
        elif variation is not None and variation.axis != "fixed":
            row[column.name] = self._vary_value(column, template_value, variation, rng)
        else:
            row[column.name] = template_value

    def _inject_noise(
        self,
        column: ColumnSchema,
        variation: ColumnVariationDTO | None,
        template_value: Any,
        row: dict[str, Any],
        rng: random.Random,
    ) -> None:
        """Inietta NULL (colonne nullable) e outlier entro i limiti dichiarati."""
        if not column.is_pk and column.nullable and rng.random() < self.null_rate:
            row[column.name] = None
        if (
            not column.is_pk
            and not column.is_fk
            and variation is not None
            and variation.axis in ("shift", "scale")
            and row[column.name] is not None
            and rng.random() < self._outlier_rate
        ):
            row[column.name] = self._outlier_value(column, template_value, variation, rng)

    @staticmethod
    def _unique_pk_value(
        column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
    ) -> Any:
        """Genera un valore PK univoco partendo dal template (sequenziale per int)."""
        return _generate_unique(column, template_value, instance_index, used)

    @staticmethod
    def _unique_value(
        column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
    ) -> Any:
        """Genera un valore UNIQUE univoco partendo dal template."""
        return _generate_unique(column, template_value, instance_index, used)

    @staticmethod
    def _vary_value(
        column: ColumnSchema, template_value: Any, variation: ColumnVariationDTO, rng: random.Random
    ) -> Any:
        """Applica l'asse di variazione dichiarato al valore del template."""
        if template_value is None:
            return None
        if variation.axis == "pool":
            return rng.choice(variation.pool)
        if variation.axis == "shift":
            delta = rng.uniform(variation.delta_min or 0, variation.delta_max or 0)
            return shift_value(template_value, column, delta)
        if variation.axis == "scale":
            factor = rng.uniform(variation.factor_min or 1, variation.factor_max or 1)
            return scale_value(template_value, factor)
        return template_value

    @staticmethod
    def _outlier_value(
        column: ColumnSchema, template_value: Any, variation: ColumnVariationDTO, rng: random.Random
    ) -> Any:
        """Valore estremo entro i confini dichiarati (per domande max/min sensate)."""
        if variation.axis == "shift":
            extreme = (
                variation.delta_max if rng.random() < _OUTLIER_COIN_FLIP else variation.delta_min
            )
            return shift_value(template_value, column, extreme or 0)
        if variation.axis == "scale":
            extreme = (
                variation.factor_max if rng.random() < _OUTLIER_COIN_FLIP else variation.factor_min
            )
            return scale_value(template_value, extreme or 1)
        return template_value
