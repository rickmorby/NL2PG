"""Eccezioni di dominio per la validazione di modelli e invarianti di business.

:author: Riccardo Morabito
"""

from typing import Any

from bench.domain.exceptions.base import BenchException


class DomainValidationError(BenchException):
    """Sollevata quando un modello o un DTO di dominio viola le regole d'invariante."""

    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        """Inizializza l'eccezione con il messaggio di errore e il payload per il logging."""
        super().__init__(message, payload)
