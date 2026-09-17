"""Porta outbound astratta per la serializzazione JSON delle run del solver.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from solver.domain.models.solver import SolverRunDTO


class SerializerPort(ABC):
    """Porta astratta per il salvataggio su disco del report JSON del solver."""

    @abstractmethod
    def save_run(self, run_dto: SolverRunDTO, output_dir: Path) -> Path:
        """Salva l'oggetto SolverRunDTO in formato JSON ad alta velocita'."""

    @abstractmethod
    def load_run(self, json_path: Path) -> SolverRunDTO:
        """Carica un file JSON di run salvato in precedenza."""
