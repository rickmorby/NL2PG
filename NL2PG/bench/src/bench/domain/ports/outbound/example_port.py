"""Porta per il caricamento degli esempi few-shot role-specific.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class ExamplePort(ABC):
    """Interfaccia per caricare esempi few-shot role-specific da filesystem."""

    @abstractmethod
    def load(self, category_id: str, role: str) -> list[dict]:
        """Carica fino a 3 esempi JSON da examples/{category_id}/{role}/ come dict."""
