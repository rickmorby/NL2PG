"""Porta outbound astratta per la generazione dei grafici scientifici del solver.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from solver.domain.models.solver import SolverRunDTO


class PlotterPort(ABC):
    """Porta astratta per la generazione delle figure PNG per l'analisi del solver."""

    @abstractmethod
    def generate_plots(self, run_dto: SolverRunDTO, output_dir: Path) -> list[Path]:
        """Genera la suite dei 6 grafici scientifici PNG nella directory specificata."""
