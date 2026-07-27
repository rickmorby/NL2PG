"""Modulo validatore applicativo per la convalida di istruzioni INSERT su PostgreSQL.

:author: Riccardo Morabito
"""

from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.models.sql import DataInsertsDTO
from bench.application.validators.schema_validator import ValidationResult


class DataValidator:
    """Validatore applicativo che verifica l'eseguibilita' delle INSERT su PostgreSQL."""

    def __init__(self, sandbox: SandboxPort):
        """Inizializza il validatore con la porta sandbox per l'esecuzione INSERT."""
        self._sandbox = sandbox

    def validate(self, inserts: DataInsertsDTO, schema: str) -> ValidationResult:
        """Esegue le INSERT nel sandbox e restituisce l'esito."""
        if not inserts.inserts.strip():
            return ValidationResult(is_valid=False, error="INSERT vuoti")
        try:
            self._sandbox.execute_inserts(schema, inserts.inserts)
            return ValidationResult()
        except Exception as e:
            return ValidationResult(is_valid=False, error=str(e))
