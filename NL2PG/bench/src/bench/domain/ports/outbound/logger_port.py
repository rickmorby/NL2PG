"""Porta astratta outbound per la configurazione del logging del sistema.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class LoggerPort(ABC):
    """Porta outbound per la gestione e l'inizializzazione del logging."""

    @abstractmethod
    def configure(self) -> None:
        """Applica la configurazione del logging."""
