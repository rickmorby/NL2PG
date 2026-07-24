"""Porta astratta outbound per la configurazione del logging del sistema.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path


class LoggerPort(ABC):
    """Porta outbound per la gestione e l'inizializzazione del logging."""

    @abstractmethod
    def configure(self) -> None:
        """Applica la configurazione del logging."""
        pass

    @abstractmethod
    def get_log_dir(self) -> Path:
        """Restituisce il percorso della directory contenente i file di log."""
        pass
