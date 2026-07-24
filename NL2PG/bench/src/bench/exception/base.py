"""Modulo base per le eccezioni personalizzate del benchmark.

:author: Riccardo Morabito
"""

from typing import Any


class BenchException(Exception):
    """Eccezione base per tutte le eccezioni del sistema di benchmark."""

    def __init__(self, message: str, payload: Any = None):
        """Inizializza l'eccezione con messaggio e payload opzionale."""
        self.message = message
        self.payload = payload
        super().__init__(message)
