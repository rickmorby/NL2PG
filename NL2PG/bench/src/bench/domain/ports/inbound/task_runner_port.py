"""Porta astratta inbound per l'esecuzione dei task batch del benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod

from bench.domain.models.document import BatchSummaryDTO


class TaskRunnerPort(ABC):
    """Porta astratta d'ingresso (Primary Port) per l'esecuzione batch dei task."""

    @abstractmethod
    def run_batch(
        self,
        count: int = 10,
        category: str = "",
        batch_size: int = 1,
    ) -> BatchSummaryDTO:
        """Esegue una run di generazione batch in modalità sequenziale o parallela."""
