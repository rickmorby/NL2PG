"""Classe astratta base per i grafici del benchmark (GoF Template Method Pattern).

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure


class AbstractPlot(ABC):
    """Classe base astratta che definisce il Template Method per la generazione dei grafici."""

    def __init__(self, figsize: tuple[float, float] = (8.0, 5.0)) -> None:
        """Inizializza la dimensione predefinita della figura."""
        self.figsize = figsize

    def render(self, tasks: list[dict[str, Any]], output_path: Path) -> None:
        """Template Method: estrae dati, disegna grafico, applica stile e salva figura."""
        data = self.prepare_data(tasks)
        fig = Figure(figsize=self.figsize)
        ax = fig.add_subplot(111)
        self.draw(ax, data)
        self.format_axes(ax)
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        fig.clf()

    @abstractmethod
    def filename(self) -> str:
        """Restituisce il nome del file PNG di output (es. '01_sql_syntax_distribution.png')."""

    @abstractmethod
    def title(self) -> str:
        """Restituisce il titolo principale del grafico."""

    @abstractmethod
    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""

    @abstractmethod
    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""

    @abstractmethod
    def prepare_data(self, tasks: list[dict[str, Any]]) -> Any:
        """Estrae e prepara i dati dai task per il grafico."""

    @abstractmethod
    def draw(self, ax: Any, data: Any) -> None:
        """Disegna il grafico sull'asse Seaborn/Matplotlib fornito."""

    def format_axes(self, ax: Any) -> None:
        """Applica la formattazione di stile base all'asse."""
        ax.set_title(self.title(), fontsize=13, fontweight="bold", pad=15, color="#2c3e50")
        ax.set_xlabel(self.xlabel(), fontsize=11, color="#34495e")
        ax.set_ylabel(self.ylabel(), fontsize=11, color="#34495e")
