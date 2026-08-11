"""Modulo base astratto per i validatori di script SQL su PostgreSQL Sandbox.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from bench.domain.models.base import AbstractDTO
from bench.domain.ports.outbound.sandbox_port import SandboxPort


@dataclass
class ValidationResult:
    """Esito della validazione di uno script SQL (DDL o INSERT)."""

    is_valid: bool = True
    error: str = ""


class AbstractSandboxValidator(ABC):
    """Base astratta per validatori nello schema Sandbox (GoF Template Method)."""

    def __init__(self, sandbox: SandboxPort) -> None:
        """Inietta la porta sandbox per l'esecuzione dello script SQL."""
        self._sandbox = sandbox

    @abstractmethod
    def _extract_sql(self, dto: AbstractDTO) -> str:
        """Estrae lo script SQL dal DTO fornito."""

    @abstractmethod
    def _execute_sql(self, schema: str, sql_text: str) -> None:
        """Esegue lo specifico comando SQL (DDL o INSERT) nello schema sandbox."""

    @abstractmethod
    def _empty_error_msg(self) -> str:
        """Restituisce il messaggio di errore per script vuoto."""

    @abstractmethod
    def _failure_error_prefix(self) -> str:
        """Restituisce il prefisso di errore per fallimento dell'esecuzione SQL."""

    def validate(self, dto: AbstractDTO, schema: str) -> ValidationResult:
        """Template Method per controllo di presenza ed esecuzione Sandbox."""
        sql_text = self._extract_sql(dto).strip()
        if not sql_text:
            return ValidationResult(is_valid=False, error=self._empty_error_msg())
        try:
            self._execute_sql(schema, sql_text)
            return ValidationResult()
        except Exception as e:
            prefix = self._failure_error_prefix()
            return ValidationResult(is_valid=False, error=f"{prefix}: {e}")
