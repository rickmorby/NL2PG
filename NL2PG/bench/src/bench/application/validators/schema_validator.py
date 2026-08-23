"""Modulo validatore applicativo per la convalida di script DDL su PostgreSQL.

:author: Riccardo Morabito
"""

from bench.application.validators.base import AbstractSandboxValidator, ValidationResult
from bench.domain.exceptions import DatabaseClientError
from bench.domain.models.base import AbstractDTO
from bench.domain.models.sql import SchemaDDLDTO
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.validation.column_type_policy import (
    find_text_monetary_columns,
    text_monetary_error,
)
from bench.domain.services.validation.identifier_policy import (
    english_identifier_error,
    find_english_identifiers,
)
from bench.domain.services.validation.schema_type_checker import SchemaTypeChecker

from psycopg.errors import Error as PgError


class SchemaValidator(AbstractSandboxValidator):
    """Validatore applicativo per l'esecuzione DDL su PostgreSQL Sandbox (GoF Template Method)."""

    def __init__(self, sandbox: SandboxPort, type_checker: SchemaTypeChecker) -> None:
        """Inietta la porta sandbox e il servizio di dominio per il tipo di schema."""
        super().__init__(sandbox)
        self._type_checker = type_checker

    def validate_with_type(
        self, dto: AbstractDTO, schema: str, tipo_schema: str
    ) -> ValidationResult:
        """Esegue il DDL nel sandbox e verifica il marcatore del tipo di schema richiesto."""
        sql_text = self._extract_sql(dto).strip()
        if not sql_text:
            return ValidationResult(is_valid=False, error=self._empty_error_msg())
        ident_hits = find_english_identifiers(sql_text)
        ident_err = english_identifier_error(ident_hits)
        if ident_err:
            return ValidationResult(is_valid=False, error=ident_err)
        money_hits = find_text_monetary_columns(sql_text)
        money_err = text_monetary_error(money_hits)
        if money_err:
            return ValidationResult(is_valid=False, error=money_err)
        type_result = self._type_checker.check(sql_text, tipo_schema)
        if not type_result.is_valid:
            return ValidationResult(is_valid=False, error=type_result.error)
        try:
            self._execute_sql(schema, sql_text)
            return ValidationResult()
        except (DatabaseClientError, PgError) as e:
            prefix = self._failure_error_prefix()
            return ValidationResult(is_valid=False, error=f"{prefix}: {e}")

    def validate_spec(self, dto: AbstractDTO, schema: str, tipo_schema: str) -> ValidationResult:
        """Alias sigillato di ``validate_with_type`` per una firma tipizzata e stabile."""
        return self.validate_with_type(dto, schema, tipo_schema)

    def table_count(self, schema: str) -> int:
        """Restituisce il numero di tabelle primarie (escluse le partizioni) create nello schema."""
        model = self._sandbox.introspect_schema(schema)
        return len([t for t in model.tables.values() if not getattr(t, "is_partition", False)])

    def _extract_sql(self, dto: AbstractDTO) -> str:
        """Estrae lo script DDL dal DTO."""
        if isinstance(dto, SchemaDDLDTO):
            return dto.ddl
        return ""

    def _execute_sql(self, schema: str, sql_text: str) -> None:
        """Esegue il DDL nello schema sandbox pulendolo prima per supportare i retry."""
        self._sandbox.reset_schema(schema)
        self._sandbox.execute_ddl(schema, sql_text)

    def _empty_error_msg(self) -> str:
        """Restituisce il messaggio per DDL vuoto."""
        return "DDL vuoto"

    def _failure_error_prefix(self) -> str:
        """Restituisce il prefisso di errore per fallimento DDL."""
        return "Esecuzione DDL fallita"
