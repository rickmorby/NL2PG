"""Porta outbound astratta per la sandbox PostgreSQL ed esecuzione DDL/SQL.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from typing import Any


class SandboxPort(ABC):
    """Porta astratta per la gestione della sandbox PostgreSQL."""

    @abstractmethod
    def create_fresh_schema(self) -> str:
        """Crea uno schema temporaneo ed isolato."""

    @abstractmethod
    def execute_ddl(self, schema: str, ddl: str) -> None:
        """Esegue istruzioni DDL per creare le tabelle nello schema."""

    @abstractmethod
    def execute_inserts(self, schema: str, inserts: str) -> None:
        """Inserisce i dati di test nello schema."""

    @abstractmethod
    def run_query(self, schema: str, query: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Esegue una query SELECT in sola lettura restituendo (colonne, righe)."""

    @abstractmethod
    def drop_schema(self, schema: str) -> None:
        """Elimina lo schema temporaneo liberando le risorse."""

    @abstractmethod
    def cleanup_orphan_schemas(self) -> list[str]:
        """Pulisce gli schemi temporanei orfani rimanenti."""
