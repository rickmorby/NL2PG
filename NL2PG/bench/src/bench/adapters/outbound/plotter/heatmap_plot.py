"""Classe base astratta specializzata per le heatmap Seaborn.

:author: Riccardo Morabito
"""

from typing import Any

from seaborn import heatmap

from bench.adapters.outbound.plotter.base import AbstractPlot


class AbstractHeatmapPlot(AbstractPlot):
    """Specializzazione di AbstractPlot per le matrici di calore (Heatmap)."""

    def __init__(
        self,
        cmap: str = "Blues",
        rotation: int = 0,
        figsize: tuple[float, float] = (8.0, 5.5),
    ) -> None:
        """Inizializza la mappa cromatica e la rotazione delle etichette."""
        super().__init__(figsize=figsize)
        self.cmap = cmap
        self.rotation = rotation

    @property
    def xticklabels(self) -> list[str] | bool:
        """Restituisce le etichette per le colonne della matrice."""
        return True

    @property
    def yticklabels(self) -> list[str] | bool:
        """Restituisce le etichette per le righe della matrice."""
        return True

    def draw(self, ax: Any, data: Any) -> None:
        """Disegna una heatmap Seaborn sull'asse fornito."""
        heatmap(
            data,
            annot=True,
            fmt="d",
            xticklabels=self.xticklabels,
            yticklabels=self.yticklabels,
            cmap=self.cmap,
            ax=ax,
        )

    def format_axes(self, ax: Any) -> None:
        """Applica il titolo, le etichette degli assi e la rotazione dei tick X."""
        super().format_axes(ax)
        if self.rotation:
            ax.tick_params(axis="x", rotation=self.rotation)
