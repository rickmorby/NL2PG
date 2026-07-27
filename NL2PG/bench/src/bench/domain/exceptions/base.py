"""Modulo base per le eccezioni personalizzate di dominio.

:author: Riccardo Morabito
"""

from logging import getLogger
from typing import Any

_log = getLogger("bench.domain.exceptions")


class BenchException(Exception):
    """Eccezione base per tutte le eccezioni del sistema di benchmark."""

    def __init__(self, message: str, payload: Any = None):
        """Inizializza l'eccezione con messaggio e payload opzionale."""
        self.message = message
        self.payload = payload
        super().__init__(message)
        try:
            _log.warning("%s: %s", type(self).__name__, self.message)
        except Exception:
            pass
