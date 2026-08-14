"""Porta per il caricamento dei template prompt.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class PromptPort(ABC):
    """Interfaccia per caricare template prompt da filesystem."""

    @abstractmethod
    def load(self, name: str, **kwargs: object) -> str:
        """Carica il template prompts/{name}.txt e lo formatta con i kwargs dati."""
