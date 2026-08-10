"""Porta astratta outbound per l'invocazione ed i test di diagnosi dei modelli LLM.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from bench.domain.models.llm import CallOptionsDTO, CallResultDTO, SystemHealthReportDTO


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

    @abstractmethod
    def check_all_providers(self) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello di tutti i provider e modelli LLM configurati."""

    @abstractmethod
    def close(self) -> None:
        """Chiude le risorse di rete ed i pool dei client LLM."""
