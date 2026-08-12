"""Porta outbound per la serializzazione dei task e dei documenti del benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path

from bench.domain.models.state import TaskStateDTO


class BenchmarkSerializerPort(ABC):
    """Porta outbound astratta per la serializzazione dei task e delle run del benchmark."""

    @abstractmethod
    def build_document(
        self,
        tasks: list[TaskStateDTO],
        run_id: str,
        weights: dict | None = None,
    ) -> dict:
        """Costruisce il documento JSON della run con tutti i task accettati."""

    @abstractmethod
    def read(self, input_path: Path) -> dict:
        """Legge e deserializza in byte UTF-8 un file JSON su filesystem."""

    @abstractmethod
    def write(self, document: dict, output_path: Path) -> None:
        """Scrive atomicamente il documento JSON su file temporaneo e lo rimpiazza."""

    @abstractmethod
    def write_single_task(self, task_dict: dict, output_path: Path) -> None:
        """Scrive atomicamente un singolo task JSON nella cartella di destinazione."""
