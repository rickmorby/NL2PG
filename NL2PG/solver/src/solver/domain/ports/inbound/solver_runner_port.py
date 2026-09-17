"""Porta astratta inbound per l'esecuzione del runner del solver sul benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path

from solver.domain.models.solver import SolverRunDTO


class SolverRunnerPort(ABC):
    """Porta astratta d'ingresso (Primary Port) per l'esecuzione del solver sul benchmark."""

    @abstractmethod
    def run_benchmark(
        self,
        benchmark_path: Path,
        recipes: list[str] | None = None,
        limit: int | None = None,
        model_role: str = "default",
        output_dir: Path | None = None,
        batch_size: int = 1,
    ) -> SolverRunDTO:
        """Esegue la valutazione del benchmark sulle ricette specificate."""
