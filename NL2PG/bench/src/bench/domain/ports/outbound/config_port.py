"""Porta per il caricamento della configurazione del benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod

from bench.domain.models.category import CategoryDTO


class ConfigPort(ABC):
    """Interfaccia per caricare configurazioni da filesystem."""

    @abstractmethod
    def load_providers(self) -> dict:
        """Carica providers.json con la configurazione dei modelli LLM."""

    @abstractmethod
    def load_bench(self) -> dict:
        """Carica bench.toml con i parametri di esecuzione; dict vuoto se assente."""

    @abstractmethod
    def load_categories(self) -> dict[str, CategoryDTO]:
        """Carica categories.json e restituisce un dict {id: CategoryDTO}."""

    @abstractmethod
    def dsn(self, key: str) -> str:
        """Restituisce il DSN per la connessione da bench.toml o fallback di default se assente."""

    @abstractmethod
    def config_hash(self, cfg: dict) -> str:
        """Calcola l'hash SHA256 di una configurazione per identificare la run."""
