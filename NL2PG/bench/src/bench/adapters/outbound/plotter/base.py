"""Classe astratta base per i grafici del benchmark (GoF Template Method Pattern).

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure


class AbstractPlot(ABC):
    """Classe base astratta che definisce il Template Method per la generazione dei grafici."""

    def __init__(
        self,
        figsize: tuple[float, float] = (9.2, 5.8),
        bottom_margin: float = 0.19,
    ) -> None:
        """Inizializza la dimensione della figura e il margine inferiore per le etichette."""
        self.figsize = figsize
        self.bottom_margin = bottom_margin

    def render(self, tasks: list[dict[str, Any]], output_path: Path) -> None:
        """Template Method: estrae dati, disegna grafico, applica spiegazione, stile ed evidenze."""
        data = self.prepare_data(tasks)
        fig = Figure(figsize=self.figsize)
        ax = fig.add_subplot(111)

        self.draw(ax, data)
        self.format_axes(ax)

        fig.suptitle(self.title(), fontsize=12, fontweight="bold", y=0.98, color="#2c3e50")
        desc = self.description()
        if desc:
            fig.text(
                0.5,
                0.93,
                desc,
                fontsize=8.5,
                fontstyle="italic",
                color="#555555",
                ha="center",
            )

        ins = self.insight(data)
        if ins:
            fig.text(
                0.5,
                0.025,
                f"Evidenza: {ins}",
                fontsize=8.5,
                color="#1a252f",
                ha="center",
                va="bottom",
                bbox={
                    "boxstyle": "round,pad=0.45",
                    "facecolor": "#f8f9fa",
                    "edgecolor": "#ced4da",
                    "alpha": 0.95,
                },
            )

        top_margin = 0.88 if desc else 0.93
        b_margin = self.bottom_margin if ins else 0.12
        fig.subplots_adjust(top=top_margin, bottom=b_margin, left=0.10, right=0.94)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300)
        fig.clf()

    @abstractmethod
    def filename(self) -> str:
        """Restituisce il nome del file PNG di output (es. '01_sql_syntax_distribution.png')."""

    @abstractmethod
    def title(self) -> str:
        """Restituisce il titolo principale del grafico."""

    def description(self) -> str:
        """Restituisce una spiegazione semplice e sintetica di cosa misura il grafico."""
        return ""

    def insight(self, _data: Any) -> str:
        """Estrae e restituisce una conclusione chiara e diretta calcolata dai dati reali."""
        return ""

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
        ax.set_xlabel(self.xlabel(), fontsize=10, color="#34495e", labelpad=8)
        ax.set_ylabel(self.ylabel(), fontsize=10, color="#34495e", labelpad=8)
