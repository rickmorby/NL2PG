"""Porta astratta inbound per l'analisi dei risultati e generazione grafici del solver.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path


class SolverAnalyticsPort(ABC):
    """Porta astratta d'ingresso (Primary Port) per la generazione di analisi e grafici."""

    @abstractmethod
    def analyze_run(self, run_json_path: Path, output_plots_dir: Path) -> list[Path]:
        """Carica un file JSON di run generato dal solver e produce la suite di grafici."""
