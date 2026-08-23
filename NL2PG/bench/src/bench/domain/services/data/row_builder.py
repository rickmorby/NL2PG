"""Costruzione della riga singola: PK/UNIQUE univoche, variazioni e rumore.

``RowBuilder`` assembla una riga applicando l'asse di variazione dichiarato,
generando valori univoci per PK e UNIQUE, iniettando rumore controllato
(NULL, outlier) e ripristinando le invarianti di riga (email anagrafica,
ordinamento temporale, non-NULL sui campi obbligatori).

:author: Riccardo Morabito
"""

from random import Random
from typing import Any, ClassVar

from bench.domain.models.data import (
    ColumnSchema,
    ColumnVariationDTO,
    TableDataSpecDTO,
    TableSchema,
)
from bench.domain.services.data.check_constraints import satisfies_check
from bench.domain.services.data.column_types import neutral_value, scale_value, shift_value
from bench.domain.services.data.email_coherence import enforce_email_coherence
from bench.domain.services.data.unique_values import generate_unique

_OUTLIER_COIN_FLIP = 0.5


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
        rng: Random,
        duplicate: bool,
    ) -> dict[str, Any]:
        """Costruisce una riga applicando variazioni, PK/UNIQUE uniche, NULL e outlier."""
        row: dict[str, Any] = {}
        for column in table.columns:
            variation = table_spec.variations.get(column.name)
            template_value = template.get(column.name)
            self._set_column_value(
                table,
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
        enforce_email_coherence(row, table, instance_index, used_unique)
        self._enforce_temporal_ordering(row)
        return row

    _DATE_PAIRS: ClassVar[list[tuple[str, str]]] = [
        ("data_inizio", "data_fine"),
        ("data_decorrenza", "data_scadenza"),
        ("data_ammissione", "data_dimissione"),
        ("data_ordine", "data_consegna"),
        ("data_ordine", "data_spedizione"),
        ("data_spedizione", "data_consegna"),
        ("data_partenza", "data_consegna"),
        ("data_partenza", "data_arrivo"),
        ("data_evento", "data_denuncia"),
        ("data_attivazione", "data_scadenza"),
        ("data_apertura", "data_chiusura"),
        ("ora_inizio", "ora_fine"),
        ("data_assunzione", "data_dimissione"),
        ("data_assunzione", "data_fine"),
        ("valid_from", "valid_to"),
    ]

    @classmethod
    def _enforce_temporal_ordering(cls, row: dict[str, Any]) -> None:
        """Garantisce la coerenza temporale tra date di inizio e fine nella stessa riga."""
        for start_key, end_key in cls._DATE_PAIRS:
            if start_key in row and end_key in row:
                s_val, e_val = row[start_key], row[end_key]
                if s_val is not None and e_val is not None and str(e_val) < str(s_val):
                    row[start_key], row[end_key] = e_val, s_val

    def _set_column_value(
        self,
        table: TableSchema,
        column: ColumnSchema,
        template_value: Any,
        variation: ColumnVariationDTO | None,
        instance_index: int,
        used_pk: dict[str, set[Any]],
        used_unique: dict[str, set[Any]],
        rng: Random,
        duplicate: bool,
        row: dict[str, Any],
    ) -> None:
        """Assegna il valore della colonna: PK, UNIQUE, FK/duplicato, variazione o template."""
        is_secondary_pk = (
            column.is_pk and len(table.pk_columns) > 1 and column.name != table.pk_columns[0]
        )
        if column.is_pk and not is_secondary_pk:
            row[column.name] = generate_unique(
                column, template_value, instance_index, used_pk[column.name]
            )
        elif column.is_unique and not column.is_fk and column.name in used_unique:
            row[column.name] = generate_unique(
                column, template_value, instance_index, used_unique[column.name]
            )
        elif column.is_fk or duplicate or is_secondary_pk:
            if is_secondary_pk and variation is not None and variation.axis != "fixed":
                val = self._vary_value(column, template_value, variation, rng)
                check = getattr(column, "check_expr", None)
                if check and not satisfies_check(val, check):
                    val = template_value
                row[column.name] = val
            else:
                row[column.name] = template_value
        elif variation is not None and variation.axis != "fixed":
            val = self._vary_value(column, template_value, variation, rng)
            check = getattr(column, "check_expr", None)
            if check and not satisfies_check(str(val), check):
                val = template_value
            row[column.name] = val
        else:
            row[column.name] = template_value

    def _inject_noise(
        self,
        column: ColumnSchema,
        variation: ColumnVariationDTO | None,
        template_value: Any,
        row: dict[str, Any],
        rng: Random,
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
            outlier = self._outlier_value(column, template_value, variation, rng)
            check = getattr(column, "check_expr", None)
            if not check or satisfies_check(str(outlier), check):
                row[column.name] = outlier

    @staticmethod
    def _vary_value(
        column: ColumnSchema, template_value: Any, variation: ColumnVariationDTO, rng: Random
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
        column: ColumnSchema, template_value: Any, variation: ColumnVariationDTO, rng: Random
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
