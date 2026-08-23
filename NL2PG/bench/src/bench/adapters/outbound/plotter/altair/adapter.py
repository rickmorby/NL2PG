"""Adattatore outbound per l'export dei grafici dichiarativi (porta ``PlotterPort``).

Itera il registro dei grafici e delega ogni rendering al Template Method
``Plot.render``: l'adattatore non conosce né i dati né la codifica grafica.
"""

from pathlib import Path
from typing import Any

from bench.adapters.outbound.plotter.altair.base import Plot
from bench.adapters.outbound.plotter.altair.plots import get_default_plots
from bench.domain.ports.outbound.plotter_port import PlotterPort


class AltairPlotterAdapter(PlotterPort):
    """Esporta i 18 grafici ufficiali come PNG @2x e SVG nella directory di run."""

    def __init__(self, plots: list[Plot] | None = None) -> None:
        """Inizializza il registro dei grafici (iniettabile per test e override)."""
        self._plots = plots if plots is not None else get_default_plots()

    def render_plots(self, tasks: list[dict[str, Any]], output_dir: Path) -> None:
        """Renderizza tutti i grafici dichiarativi nella directory del run."""
        output_dir.mkdir(parents=True, exist_ok=True)
        for plot in self._plots:
            plot.render(tasks, output_dir / plot.filename())
