"""Porta astratta outbound per l'invocazione dei modelli LLM.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO


class LLMGeneratorPort(ABC):
    """Porta outbound per l'invocazione di modelli LLM con failover automatico."""

    @abstractmethod
    def get_chain(self, role: str) -> list[str]:
        """Restituisce la lista dei model_id configurati per un ruolo."""

    @abstractmethod
    def call_model(
        self,
        role: str,
        prompt: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> CallResultDTO:
        """Chiama la catena LLM con failover automatico tra modelli."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Chiude le risorse di rete ed i pool dei client LLM."""
        pass
