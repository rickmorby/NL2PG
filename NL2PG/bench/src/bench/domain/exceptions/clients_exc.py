"""Modulo delle eccezioni relative ai client di infrastruttura e adattatori.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException


class DatabaseClientError(BenchException):
    """Errore sollevato durante le operazioni sul database PostgreSQL."""


class LLMClientError(BenchException):
    """Errore sollevato durante le chiamate o i failover ai modelli LLM."""

    def __init__(self, message: str, kind: str = "", failovers: list | None = None, payload=None):
        """Inizializza l'eccezione con kind e failovers opzionali."""
        self.kind = kind
        self.failovers = failovers or []
        super().__init__(message, payload=payload)


class ProviderConfigError(BenchException):
    """Sollevata se il file di configurazione dei provider è assente o non valido."""
