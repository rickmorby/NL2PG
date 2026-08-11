"""Porta astratta inbound per la generazione delle metriche ed orchestrazione grafica.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path

from bench.domain.models.analytics import AnalyticsDTO


class AnalyticsServicePort(ABC):
    """Porta astratta d'ingresso (Primary Port) per la generazione di analytics e grafici."""

    @abstractmethod
    def generate_analytics(self, target_path: Path) -> AnalyticsDTO:
        """Coordina la lettura dei task, il calcolo delle metriche ed il salvataggio dei grafici."""
