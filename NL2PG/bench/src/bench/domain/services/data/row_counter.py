"""Calcolo dei volumi di generazione per tabella.

``RowCounter`` determina il numero di righe di ciascuna tabella a partire
dalla natura dichiarata (range di default), da un range esplicito o dal
moltiplicatore per-parent, applicando poi il limite massimo di righe per
tabella e per task.

:author: Riccardo Morabito
"""

from random import Random

from bench.domain.models.data import DataSpecDTO, SchemaModel, TableDataSpecDTO, TableSchema
from bench.domain.services.data.data_spec_validator import DataSpecValidationError
from bench.domain.services.data.foreign_key_binder import table_order

_DEFAULT_NATURE_RANGES: dict[str, tuple[int, int]] = {
    "lookup": (5, 50),
    "dimension": (100, 800),
    "fact": (300, 3000),
}


class RowCounter:
    """Calcola il numero di righe per tabella (natura, range o moltiplicatore FK)."""

    def __init__(
        self,
        nature_ranges: dict[str, tuple[int, int]] | None = None,
        max_rows_per_table: int = 3000,
        max_total_rows: int = 30000,
    ) -> None:
        """Inietta i range di natura e i limiti di volume (sezione [data])."""
        self._nature_ranges = nature_ranges or dict(_DEFAULT_NATURE_RANGES)
        self._max_rows_per_table = max_rows_per_table
        self._max_total_rows = max_total_rows

    def compute(self, spec: DataSpecDTO, schema: SchemaModel, rng: Random) -> dict[str, int]:
        """Calcola i conteggi per tabella in ordine topologico (padri prima)."""
        counts: dict[str, int] = {}
        specs = {t.table.lower(): t for t in spec.tables}
        for name in table_order(schema):
            table_spec = specs.get(name)
            if table_spec is None:
                continue
            table = schema.table(name)
            count = self._base_count(table_spec, rng)
            count = self._apply_parent_multiplier(table_spec, table, counts, count, rng)
            counts[name] = min(count, self._max_rows_per_table)
        total = sum(counts.values())
        if total > self._max_total_rows:
            raise DataSpecValidationError(
                f"Totale righe {total} supera il limite {self._max_total_rows}"
            )
        return counts

    def _base_count(self, table_spec: TableDataSpecDTO, rng: Random) -> int:
        """Conteggio di base: range esplicito oppure range della natura."""
        if table_spec.nature == "explicit":
            lo, hi = table_spec.min_rows, table_spec.max_rows
            return rng.randint(lo or 1, hi or 1)
        lo, hi = self._nature_ranges.get(table_spec.nature, (5, 50))
        return rng.randint(lo, hi)

    @staticmethod
    def _apply_parent_multiplier(
        table_spec: TableDataSpecDTO,
        table: TableSchema,
        counts: dict[str, int],
        count: int,
        rng: Random,
    ) -> int:
        """Moltiplica per il numero di righe del padre quando dichiarato."""
        pk_fk = {c.name for c in table.columns if c.is_pk and c.is_fk}
        if pk_fk:
            parent_tbl = next((c.fk_parent_table for c in table.columns if c.name in pk_fk), None)
            if parent_tbl:
                parent_count = counts.get(parent_tbl.lower(), 0)
                if parent_count > 0:
                    return min(count, parent_count)
        parent = table.fk_columns[0] if len(table.fk_columns) == 1 else None
        if parent is None or table_spec.per_parent_rows is None:
            return count
        parent_count = counts.get(parent.fk_parent_table or "", 0)
        if parent_count <= 0:
            return count
        jitter = rng.uniform(0.9, 1.1)
        return max(1, round(parent_count * table_spec.per_parent_rows * jitter))
