"""Porta astratta outbound per l'amministrazione degli schemi temporanei sandbox.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator

from bench.domain.models.data import SchemaModel


class SandboxPort(ABC):
    """Porta outbound per l'amministrazione degli schemi temporanei sandbox ed esecuzione AST."""

    @abstractmethod
    def create_fresh_schema(self) -> str:
        """Crea uno schema temporaneo univoco isolato per un task."""

    @abstractmethod
    def execute_ddl(self, schema: str, ddl: str) -> None:
        """Valida l'AST ed esegue lo script DDL nello schema temporaneo."""

    @abstractmethod
    def execute_inserts(self, schema: str, inserts: str) -> None:
        """Valida l'AST ed inserisce i dati sintetici nello schema temporaneo."""

    @abstractmethod
    def introspect_schema(self, schema: str) -> SchemaModel:
        """Restituisce il modello dello schema (tabelle, colonne, PK, FK) da information_schema."""

    @abstractmethod
    def run_query(self, schema: str, query: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Valida l'AST ed esegue la query SELECT nello schema temporaneo."""

    @abstractmethod
    def drop_schema(self, schema: str) -> None:
        """Elimina uno schema temporaneo e le relative tabelle."""

    @abstractmethod
    def test_data_mutation(
        self, schema: str, query: str, tables: list[str], attempts: int = 3
    ) -> tuple[bool, str]:
        """Verifica se una query SQL e' sensibile a mutazioni dei dati nel sandbox."""

    @abstractmethod
    def cleanup_orphan_schemas(self) -> list[str]:
        """Elimina tutti gli schemi temporanei orfani (task_*) nel database sandbox."""

    @abstractmethod
    @contextmanager
    def task_scope(self, schema: str | None = None) -> Generator[str, None, None]:
        """Context manager per l'allocazione e distruzione automatica dello schema."""
