"""Porte astratte outbound per l'interazione con il database PostgreSQL ed il sandbox.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator


class DatabasePort(ABC):
    """Porta outbound per le operazioni di trasporto a basso livello sul database PostgreSQL."""

    @abstractmethod
    def get_meta_connection(self) -> Generator[Any, None, None]:
        """Ottiene una connessione al database dei metadati."""
        pass

    @abstractmethod
    def get_sandbox_connection(
        self, schema: str = "", autocommit: bool = False
    ) -> Generator[Any, None, None]:
        """Ottiene una connessione al database sandbox."""
        pass

    @abstractmethod
    def execute_prepared(
        self,
        conn: Any,
        statement: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> None:
        """Esegue uno statement o comando SQL parametrizzato/prepared."""
        pass

    @abstractmethod
    def execute_identifier(self, conn: Any, template: str, identifier: str) -> None:
        """Esegue un comando DDL inserendo un identificatore dinamico sicuro."""
        pass

    @abstractmethod
    def execute_query(
        self,
        conn: Any,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Esegue una query SELECT di lettura parametrizzata in modalità read-only."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Chiude le risorse di connessione ed i pool."""
        pass


class SandboxPort(ABC):
    """Porta outbound per l'amministrazione degli schemi temporanei sandbox ed esecuzione AST."""

    @abstractmethod
    def create_fresh_schema(self) -> str:
        """Crea uno schema temporaneo univoco isolato per un task."""
        pass

    @abstractmethod
    def execute_ddl(self, schema: str, ddl: str) -> None:
        """Valida l'AST ed esegue lo script DDL nello schema temporaneo."""
        pass

    @abstractmethod
    def execute_inserts(self, schema: str, inserts: str) -> None:
        """Valida l'AST ed inserisce i dati sintetici nello schema temporaneo."""
        pass

    @abstractmethod
    def run_query(self, schema: str, query: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Valida l'AST ed esegue la query SELECT nello schema temporaneo."""
        pass

    @abstractmethod
    def drop_schema(self, schema: str) -> None:
        """Elimina uno schema temporaneo e le relative tabelle."""
        pass

    @abstractmethod
    @contextmanager
    def task_scope(self, schema: str | None = None) -> Generator[str, None, None]:
        """Context manager per l'allocazione e distruzione automatica dello schema."""
        pass
