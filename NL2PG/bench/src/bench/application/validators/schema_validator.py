"""Modulo validatore applicativo per la convalida di script DDL su PostgreSQL.

:author: Riccardo Morabito
"""

from bench.application.validators.base import AbstractSandboxValidator
from bench.domain.models.base import AbstractDTO
from bench.domain.models.sql import SchemaDDLDTO


class SchemaValidator(AbstractSandboxValidator):
    """Validatore applicativo per l'esecuzione DDL su PostgreSQL Sandbox (GoF Template Method)."""

    def _extract_sql(self, dto: AbstractDTO) -> str:
        """Estrae lo script DDL dal DTO."""
        if isinstance(dto, SchemaDDLDTO):
            return dto.ddl
        return ""

    def _execute_sql(self, schema: str, sql_text: str) -> None:
        """Esegue il DDL nello schema sandbox."""
        self._sandbox.execute_ddl(schema, sql_text)

    def _empty_error_msg(self) -> str:
        """Restituisce il messaggio per DDL vuoto."""
        return "DDL vuoto"

    def _failure_error_prefix(self) -> str:
        """Restituisce il prefisso di errore per fallimento DDL."""
        return "Esecuzione DDL fallita"
