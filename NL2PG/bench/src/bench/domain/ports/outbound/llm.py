"""Porta astratta outbound per l'istanziazione e l'orchestrazione dei modelli LLM.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from langchain_core.runnables import Runnable
from pydantic import BaseModel
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO


class LLMGeneratorPort(ABC):
    """Porta outbound per la generazione di contenuti e l'orchestrazione delle catene LLM."""

    @abstractmethod
    def create_model_runnable(
        self,
        model_id: str,
        schema: type[BaseModel] | type,
        temperature_override: float | None = None,
        attempts: int = 3,
    ) -> Runnable:
        """Crea un Runnable per un singolo modello con output strutturato e retry nativo."""
        pass

    @abstractmethod
    def build_chain_runnable(
        self,
        role: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> Runnable:
        """Costruisce una catena Runnable completa provvista di fallbacks nativi tra modelli."""
        pass

    @abstractmethod
    def call_model(
        self,
        role: str,
        prompt: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> CallResultDTO:
        """Esegue l'invocazione della catena LLM per un dato ruolo e restituisce CallResultDTO."""
        pass
