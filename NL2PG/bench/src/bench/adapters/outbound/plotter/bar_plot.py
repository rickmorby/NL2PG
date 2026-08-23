"""Classe base astratta specializzata per i barplot Seaborn.

:author: Riccardo Morabito
"""

from typing import Any

from seaborn import barplot

from bench.adapters.outbound.plotter.base import AbstractPlot

_SMALL_MAX_ITEMS = 20
_MEDIUM_MAX_ITEMS = 30
_HEADROOM_FACTOR = 1.15


class AbstractBarPlot(AbstractPlot):
    """Specializzazione di AbstractPlot per i grafici a barre."""

    def __init__(
        self,
        palette: str | list[str] = "colorblind",
        rotation: int = 0,
        ylim: tuple[float, float] | None = None,
        figsize: tuple[float, float] = (9.2, 5.8),
        bottom_margin: float | None = None,
    ) -> None:
        """Inizializza le opzioni di palette, rotazione e limiti Y per i barplot."""
        b_margin = bottom_margin or (0.28 if rotation > 0 else 0.19)
        super().__init__(figsize=figsize, bottom_margin=b_margin)
        self.palette = palette
        self.rotation = rotation
        self.ylim = ylim
        self._max_data_val: float = 1.0

    def _adapt_layout(self, n_items: int) -> None:
        """Adatta dimensioni, rotazione e margini al numero di etichette sull'asse X."""
        self._label_count = n_items
        if n_items <= _SMALL_MAX_ITEMS:
            self.figsize = (9, 5.5)
            self.rotation = 35
            self.bottom_margin = 0.28
        elif n_items <= _MEDIUM_MAX_ITEMS:
            self.figsize = (11.5, 6)
            self.rotation = 65
            self.bottom_margin = 0.32
        else:
            self.figsize = (14, 6.5)
            self.rotation = 75
            self.bottom_margin = 0.36

    def draw(self, ax: Any, data: tuple[list[Any], list[Any]]) -> None:
        """Disegna un barplot Seaborn annotando ogni barra con il valore numerico."""
        xs, ys = data
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette=self.palette)
        has_floats = any(isinstance(v, float) for v in ys)
        fmt = "%.2f" if has_floats else "%g"
        label_fs = 7.5 if getattr(self, "_label_count", 0) > _MEDIUM_MAX_ITEMS else 9
        numeric_ys = [v for v in ys if isinstance(v, (int, float))]
        self._max_data_val = max(numeric_ys, default=1.0)
        for c in ax.containers:
            ax.bar_label(c, padding=3, fmt=fmt, fontsize=label_fs)

    def format_axes(self, ax: Any) -> None:
        """Applica il titolo, le etichette degli assi e la rotazione dei tick X.

        L'headroom del 15% viene applicato SEMPRE per ultima per garantire che le
        etichette ``bar_label`` non escano mai dal riquadro del grafico.
        """
        super().format_axes(ax)
        if self.ylim:
            lower, upper = self.ylim[0], self.ylim[1] * _HEADROOM_FACTOR
        else:
            lower, upper = 0, self._max_data_val * _HEADROOM_FACTOR
        ax.set_ylim(lower, upper)
        if self.rotation:
            ax.tick_params(axis="x", rotation=self.rotation)
            for tick in ax.get_xticklabels():
                tick.set_ha("right")
