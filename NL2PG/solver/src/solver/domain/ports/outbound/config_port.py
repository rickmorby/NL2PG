"""Porta outbound astratta per l'accesso alla configurazione del solver.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ConfigPort(ABC):
    """Porta astratta per la lettura della configurazione del solver."""

    @abstractmethod
    def load_providers(self) -> dict[str, Any]:
        """Restituisce la configurazione dei provider LLM."""

    @abstractmethod
    def solver_max_tool_iterations(self) -> int:
        """Restituisce il numero massimo di iterazioni di tool calling."""

    @abstractmethod
    def solver_max_retries(self) -> int:
        """Restituisce il numero massimo di tentativi di ripristino per task."""

    @abstractmethod
    def solver_temperature(self) -> float:
        """Restituisce la temperatura di generazione per il solver."""

    @abstractmethod
    def dsn(self, key: str) -> str:
        """Restituisce il DSN di connessione al database PostgreSQL."""

    @abstractmethod
    def qdrant_url(self) -> str:
        """Restituisce l'URL di connessione al database vettoriale Qdrant."""

    @abstractmethod
    def rag_collection_name(self) -> str:
        """Restituisce il nome della collezione di default in Qdrant."""

    @abstractmethod
    def embedding_model(self) -> str:
        """Restituisce il nome del modello di embedding configurato."""

    @abstractmethod
    def load_rag_dir(self) -> Path:
        """Restituisce il percorso configurato della cartella per RAG."""

    @abstractmethod
    def default_benchmark_path(self) -> Path | None:
        """Restituisce il percorso di default per il file di benchmark."""
