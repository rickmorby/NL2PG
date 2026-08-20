"""Servizio di dominio per la materializzazione deterministica dei dati sintetici.

``DataMaterializer`` e' una facade che compone collaboratori a responsabilita'
singola: ``DataSpecValidator`` (regole rispetto allo schema), ``RowCounter``
(volumi per natura/range/moltiplicatore), ``RowExpander`` e ``RowBuilder``
(espansione template con rumore), ``ForeignKeyBinder`` (binding a PK reali e
dedupe delle PK composite), ``InsertScriptBuilder`` (script a batch) e
``DataProfileBuilder`` (profilo compatto per gli agenti a valle).

La pipeline e' deterministica per seed: stessa DataSpec + stesso seed ->
stesse righe, stesso script e stesso profilo.

:author: Riccardo Morabito
"""

from random import Random
from typing import Any

from bench.domain.models.data import DataSpecDTO, SchemaModel
from bench.domain.services.data.data_profile_builder import DataProfileBuilder
from bench.domain.services.data.data_spec_validator import DataSpecValidator
from bench.domain.services.data.foreign_key_binder import ForeignKeyBinder
from bench.domain.services.data.insert_script_builder import InsertScriptBuilder
from bench.domain.services.data.row_counter import RowCounter
from bench.domain.services.data.row_generation import RowExpander


class MaterializationResult:
    """Esito della materializzazione: script INSERT, profilo dati e righe strutturate."""

    def __init__(
        self,
        insert_script: str,
        profile: dict[str, Any],
        rows: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Inizializza l'esito con script, profilo e righe."""
        self.insert_script = insert_script
        self.profile = profile
        self.rows = rows


class DataMaterializer:
    """Espande una DataSpec in righe deterministiche conformi allo schema."""

    def __init__(
        self,
        nature_ranges: dict[str, tuple[int, int]] | None = None,
        max_rows_per_table: int = 3000,
        max_total_rows: int = 30000,
        batch_size: int = 100,
        null_rate: float = 0.05,
        dup_rate: float = 0.03,
        outlier_rate: float = 0.02,
    ) -> None:
        """Inietta i parametri (sezione [data]) e compone i collaboratori di dominio."""
        self._validator = DataSpecValidator(max_rows_per_table=max_rows_per_table)
        self._counter = RowCounter(nature_ranges, max_rows_per_table, max_total_rows)
        self._expander = RowExpander(null_rate, dup_rate, outlier_rate)
        self._binder = ForeignKeyBinder(null_rate)
        self._script_builder = InsertScriptBuilder(batch_size)
        self._profile_builder = DataProfileBuilder()

    def materialize(
        self, spec: DataSpecDTO, schema: SchemaModel, seed: int
    ) -> MaterializationResult:
        """Materializza la spec in script INSERT, profilo e righe strutturate."""
        self._validator.validate(spec, schema)
        rng = Random(seed)
        counts = self._counter.compute(spec, schema, rng)
        rows = self._expander.expand(spec, schema, counts, rng)
        self._binder.bind(schema, rows, rng)
        self._binder.dedupe_composite_keys(schema, rows, rng)
        script = self._script_builder.build(schema, rows)
        profile = self._profile_builder.build(rows)
        return MaterializationResult(insert_script=script, profile=profile, rows=rows)
