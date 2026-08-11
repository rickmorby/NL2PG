"""Modulo validatore applicativo per la convalida di istruzioni INSERT su PostgreSQL.

:author: Riccardo Morabito
"""

from bench.application.validators.base import AbstractSandboxValidator
from bench.domain.models.base import AbstractDTO
from bench.domain.models.sql import DataInsertsDTO


class DataValidator(AbstractSandboxValidator):
    """Validatore applicativo per le INSERT su PostgreSQL Sandbox (GoF Template Method)."""

    def _extract_sql(self, dto: AbstractDTO) -> str:
        """Estrae lo script INSERT dal DTO."""
        if isinstance(dto, DataInsertsDTO):
            return dto.inserts
        return ""

    def _execute_sql(self, schema: str, sql_text: str) -> None:
        """Esegue le INSERT nello schema sandbox."""
        self._sandbox.execute_inserts(schema, sql_text)

    def _empty_error_msg(self) -> str:
        """Restituisce il messaggio per INSERT vuote."""
        return "INSERT vuoti"

    def _failure_error_prefix(self) -> str:
        """Restituisce il prefisso di errore per fallimento INSERT."""
        return "Inserimento dati fallito"
