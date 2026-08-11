"""Porta astratta inbound per la promozione dei task accettati nelle directory di esempio.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path


class TaskPromoterPort(ABC):
    """Porta astratta d'ingresso (Primary Port) per la promozione dei task accettati."""

    @abstractmethod
    def promote_accepted_tasks(self, output_dir: Path, examples_dir: Path) -> int:
        """Legge i file JSON di run da output_dir e li promuove in examples/<cat>/."""
