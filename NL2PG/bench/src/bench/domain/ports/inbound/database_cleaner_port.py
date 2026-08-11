"""Porta astratta inbound per la pulizia degli schemi temporanei nel database sandbox.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class DatabaseCleanerPort(ABC):
    """Porta astratta d'ingresso (Primary Port) per la pulizia degli schemi sandbox orfani."""

    @abstractmethod
    def cleanup_sandbox_schemas(self) -> list[str]:
        """Elimina gli schemi temporanei orfani task_* e ne restituisce l'elenco."""
