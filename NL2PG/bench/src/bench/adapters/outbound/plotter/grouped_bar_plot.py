"""Classe base astratta specializzata per i barplot raggruppati (hue) Seaborn.

:author: Riccardo Morabito
"""

from typing import Any

from seaborn import barplot

from bench.adapters.outbound.plotter.base import AbstractPlot

_SMALL_MAX_ITEMS = 8
_MEDIUM_MAX_ITEMS = 16


class AbstractGroupedBarPlot(AbstractPlot):
    """Specializzazione di AbstractPlot per i barplot con gruppi (hue binario o multi)."""

    def __init__(
        self,
        palette: str | list[str] = "colorblind",
        rotation: int = 0,
        ylim: tuple[float, float] | None = None,
        figsize: tuple[float, float] = (9.2, 5.8),
        bottom_margin: float | None = None,
    ) -> None:
        """Inizializza palette, rotazione e limiti Y per i barplot raggruppati."""
        b_margin = bottom_margin or (0.28 if rotation > 0 else 0.19)
        super().__init__(figsize=figsize, bottom_margin=b_margin)
        self.palette = palette
        self.rotation = rotation
        self.ylim = ylim

    def _adapt_layout(self, n_items: int) -> None:
        """Adatta dimensioni, rotazione e margini al numero di gruppi sull'asse X."""
        self._label_count = n_items
        if n_items <= _SMALL_MAX_ITEMS:
            self.figsize = (11, 6)
            self.rotation = 35
            self.bottom_margin = 0.28
        elif n_items <= _MEDIUM_MAX_ITEMS:
            self.figsize = (13, 6.5)
            self.rotation = 45
            self.bottom_margin = 0.30
        else:
            self.figsize = (15, 7)
            self.rotation = 60
            self.bottom_margin = 0.34

    def draw(
        self,
        ax: Any,
        data: tuple[list[str], dict[str, list[Any]]],
    ) -> None:
        """Disegna un barplot Seaborn raggruppato per hue, annotando ogni barra.

        ``data`` è una tupla ``(categorie, conteggi_per_gruppo)`` dove le chiavi
        del dizionario sono i gruppi (es. Easy/Hard) e le liste hanno un valore
        per ogni categoria.
        """
        categories, by_group = data
        xs: list[str] = []
        ys: list[Any] = []
        hues: list[str] = []
        for group in by_group:
            for i, category in enumerate(categories):
                xs.append(category)
                ys.append(by_group[group][i])
                hues.append(group)
        barplot(x=xs, y=ys, hue=hues, ax=ax, palette=self.palette, legend=False)
        ax.legend(
            title="Difficoltà",
            loc="upper right",
            frameon=False,
            fontsize=8,
            title_fontsize=9,
        )
        has_floats = any(isinstance(v, float) for v in ys)
        fmt = "%.2f" if has_floats else "%g"
        label_fs = 7.5 if getattr(self, "_label_count", 0) > _MEDIUM_MAX_ITEMS else 9
        for container in ax.containers:
            ax.bar_label(container, padding=3, fmt=fmt, fontsize=label_fs)

    def format_axes(self, ax: Any) -> None:
        """Applica il titolo, le etichette degli assi e la rotazione dei tick X."""
        super().format_axes(ax)
        if self.ylim:
            ax.set_ylim(*self.ylim)
        if self.rotation:
            ax.tick_params(axis="x", rotation=self.rotation)
            for tick in ax.get_xticklabels():
                tick.set_ha("right")
