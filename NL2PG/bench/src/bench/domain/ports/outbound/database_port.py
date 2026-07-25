"""Porta astratta outbound per il trasporto a basso livello sul database PostgreSQL.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
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
