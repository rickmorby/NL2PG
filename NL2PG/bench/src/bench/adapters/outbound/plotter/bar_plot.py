"""Classe base astratta specializzata per i barplot Seaborn.

:author: Riccardo Morabito
"""

from typing import Any

from seaborn import barplot

from bench.adapters.outbound.plotter.base import AbstractPlot


class AbstractBarPlot(AbstractPlot):
    """Specializzazione di AbstractPlot per i grafici a barre."""

    def __init__(
        self,
        palette: str | list[str] = "colorblind",
        rotation: int = 0,
        ylim: tuple[float, float] | None = None,
        figsize: tuple[float, float] = (8.0, 5.0),
    ) -> None:
        """Inizializza le opzioni di palette, rotazione e limiti Y per i barplot."""
        super().__init__(figsize=figsize)
        self.palette = palette
        self.rotation = rotation
        self.ylim = ylim

    def draw(self, ax: Any, data: tuple[list[Any], list[Any]]) -> None:
        """Disegna un barplot Seaborn annotando ogni barra con il valore numerico."""
        xs, ys = data
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette=self.palette)
        has_floats = any(isinstance(v, float) for v in ys)
        fmt = "%.2f" if has_floats else "%g"
        for c in ax.containers:
            ax.bar_label(c, padding=3, fmt=fmt, fontsize=9)

    def format_axes(self, ax: Any) -> None:
        """Applica il titolo, le etichette degli assi e la rotazione dei tick X."""
        super().format_axes(ax)
        if self.ylim:
            ax.set_ylim(*self.ylim)
        if self.rotation:
            ax.tick_params(axis="x", rotation=self.rotation)
