"""Validazione della DataSpec contro il modello di schema relazionale.

Il validatore verifica solo le regole che dipendono dallo schema o dalla
configurazione (tabelle esistenti, colonne reali, FK del moltiplicatore,
limite massimo di righe). Le regole strutturali (natura, asse, range
esplicito, template non vuoti, pool valorizzato) sono dichiarate nei DTO
Pydantic e falliscono gia' al parsing dell'output LLM.

:author: Riccardo Morabito
"""

from logging import getLogger
from typing import Any

from bench.domain.exceptions.domain_exc import DomainValidationError
from bench.domain.models.data import (
    DataSpecDTO,
    SchemaModel,
    TableDataSpecDTO,
    TableSchema,
)

_log = getLogger("bench.domain.data_spec_validator")


class DataSpecValidationError(DomainValidationError):
    """Sollevata quando la DataSpec viola le regole rispetto allo schema."""


class DataSpecValidator:
    """Verifica la DataSpec rispetto allo schema relazionale e ai limiti configurati."""

    def __init__(self, max_rows_per_table: int = 3000) -> None:
        """Inietta il limite massimo di righe per tabella (sezione [data])."""
        self._max_rows_per_table = max_rows_per_table

    def validate(self, spec: DataSpecDTO, schema: SchemaModel) -> None:
        """Verifica ogni voce della spec contro le tabelle dello schema."""
        for table_spec in spec.tables:
            table = schema.table(table_spec.table)
            if table is None:
                raise DataSpecValidationError(
                    f"Tabella '{table_spec.table}' non presente nello schema"
                )
            self._validate_table_spec(table_spec, table)

    def _validate_table_spec(self, table_spec: TableDataSpecDTO, table: TableSchema) -> None:
        """Verifica limite righe, template e variazioni di una singola voce."""
        if table_spec.max_rows is not None and table_spec.max_rows > self._max_rows_per_table:
            raise DataSpecValidationError(
                f"max_rows di '{table_spec.table}' supera il limite {self._max_rows_per_table}"
            )
        for template in table_spec.templates:
            self._validate_template(table_spec, table, template)
        for column_name in table_spec.variations:
            self._validate_variation(table_spec, table, column_name)
        if table_spec.per_parent_rows is not None:
            self._validate_per_parent(table_spec, table)

    @staticmethod
    def _validate_template(
        table_spec: TableDataSpecDTO, table: TableSchema, template: dict[str, Any]
    ) -> None:
        """Verifica le chiavi del template; rimuove colonne sconosciute con warning."""
        unknown = [key for key in template if table.column(key) is None]
        if unknown:
            for key in unknown:
                template.pop(key, None)
            _log.warning(
                "Template di '%s' conteneva colonne sconosciute %s — rimosse",
                table_spec.table,
                unknown,
            )
            if not template:
                raise DataSpecValidationError(
                    f"Template di '{table_spec.table}' vuoto dopo "
                    f"rimozione colonne sconosciute {unknown}"
                )

    @staticmethod
    def _validate_variation(
        table_spec: TableDataSpecDTO, table: TableSchema, column_name: str
    ) -> None:
        """Verifica che la variazione riguardi una colonna reale della tabella."""
        if table.column(column_name) is None:
            raise DataSpecValidationError(
                f"Variazione su colonna sconosciuta '{column_name}' in '{table_spec.table}'"
            )

    @staticmethod
    def _validate_per_parent(table_spec: TableDataSpecDTO, table: TableSchema) -> None:
        """Verifica il moltiplicatore per-parent; auto-ripara se FK non singola."""
        if len(table.fk_columns) != 1:
            _log.warning(
                "'per_parent_rows' su '%s' richiede 1 FK (trovate %d) — ignorato",
                table_spec.table,
                len(table.fk_columns),
            )
            table_spec.per_parent_rows = None
            return
        fk = table.fk_columns[0]
        if fk.fk_parent_table == table.name:
            _log.warning(
                "'per_parent_rows' non ammesso su self-reference '%s' — ignorato",
                table.name,
            )
            table_spec.per_parent_rows = None
            return
