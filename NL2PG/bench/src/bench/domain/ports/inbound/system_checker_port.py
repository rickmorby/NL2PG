"""Porta astratta inbound per la diagnosi del sistema ed i controlli dei provider LLM.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod

from bench.domain.models.llm import ConfigCheckResultDTO, SystemHealthReportDTO


class SystemCheckPort(ABC):
    """Porta astratta d'ingresso (Primary Port) per la diagnosi ed i controlli di integrità."""

    @abstractmethod
    def check_configurations(self) -> ConfigCheckResultDTO:
        """Carica le configurazioni e ne calcola gli hash di integrità."""

    @abstractmethod
    def check_llm_providers(self, check_models: bool = True) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello di tutti i provider e modelli configurati."""
