"""Modulo delle eccezioni relative ai client di infrastruttura e adattatori.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException


class DatabaseClientError(BenchException):
    """Errore sollevato durante le operazioni sul database PostgreSQL."""


class LLMClientError(BenchException):
    """Errore sollevato durante le chiamate o i failover ai modelli LLM."""


class ProviderConfigError(BenchException):
    """Sollevata se il file di configurazione dei provider è assente o non valido."""


class ModelOutputContractError(BenchException):
    """Sollevata quando l'output dell'LLM viola lo schema Pydantic o i vincoli del contratto di dominio."""
