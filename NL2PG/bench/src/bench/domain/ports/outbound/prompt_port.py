"""Porta per il caricamento dei template prompt.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class PromptPort(ABC):
    """Interfaccia per caricare template prompt da filesystem."""

    @abstractmethod
    def load(self, name: str, **kwargs: object) -> str:
        """Carica il template prompts/{name}.txt e lo formatta con i kwargs dati."""

    @abstractmethod
    def few_shot(self, category_id: str) -> str:
        """Carica fino a 3 esempi YAML da examples/{category_id}/ per few-shot."""