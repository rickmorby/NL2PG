"""Modulo validatore applicativo per la convalida di script DDL su PostgreSQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.models.sql import SchemaDDLDTO


@dataclass
class ValidationResult:
    """Esito della validazione di uno script DDL o INSERT."""

    is_valid: bool = True
    error: str = ""


class SchemaValidator:
    """Validatore applicativo che verifica l'eseguibilita' di uno script DDL su PostgreSQL."""

    def __init__(self, sandbox: SandboxPort):
        """Inizializza il validatore con la porta sandbox per l'esecuzione DDL."""
        self._sandbox = sandbox

    def validate(self, ddl: SchemaDDLDTO, schema: str) -> ValidationResult:
        """Esegue il DDL nel sandbox e restituisce l'esito."""
        if not ddl.ddl.strip():
            return ValidationResult(is_valid=False, error="DDL vuoto")
        try:
            self._sandbox.execute_ddl(schema, ddl.ddl)
            return ValidationResult()
        except Exception as e:
            return ValidationResult(is_valid=False, error=f"Esecuzione DDL fallita: {e}")
