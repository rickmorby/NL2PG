"""Modulo base per i client di infrastruttura.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from typing import Any


class DatabaseClientInterface(ABC):
    """Interfaccia per il client di trasporto PostgreSQL a basso livello."""

    @abstractmethod
    def get_meta_connection(self) -> Any:
        """Apre e restituisce una connessione al database dei metadati."""
        pass

    @abstractmethod
    def get_sandbox_connection(self, schema: str = "", autocommit: bool = False) -> Any:
        """Apre e restituisce una connessione al database sandbox con search_path isolato."""
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
        """Esegue un comando DDL usando identificatori sicuri contro SQL Injection."""
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
        """Chiude le risorse di connessione gestite dal client."""
        pass


class AbstractClient(ABC):
    """Classe base astratta per tutti i client di infrastruttura."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Inizializza il client memorizzando la configurazione."""
        self._config = config or {}

    def get_config(self) -> dict[str, Any]:
        """Restituisce la configurazione del client."""
        return self._config
