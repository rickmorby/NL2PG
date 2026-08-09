"""Adattatore outbound per il rendering polimorfico dei 16 grafici con Seaborn (OOP Pattern).

:author: Riccardo Morabito
"""

from pathlib import Path
from typing import Any

from bench.adapters.outbound.plotter.base import AbstractPlot
from bench.adapters.outbound.plotter.plots import get_default_plots
from bench.domain.ports.outbound.plotter_port import PlotterPort
from bench.domain.services.analytics_calculator import AnalyticsCalculator


class SeabornPlotterAdapter(PlotterPort):
    """Adattatore concreto per il rendering dei 16 grafici con la libreria Seaborn."""

    def __init__(
        self,
        calculator: AnalyticsCalculator | None = None,
        plots: list[AbstractPlot] | None = None,
    ) -> None:
        """Inizializza l'adattatore grafico ed il registro dei 16 grafici polimorfici."""
        calc = calculator or AnalyticsCalculator()
        self._plots = plots or get_default_plots(calc)

    def render_plots(self, tasks: list[dict[str, Any]], output_dir: Path) -> None:
        """Renderizza e salva i 16 grafici scientifici polimorficamente nella directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        for plot in self._plots:
            plot.render(tasks, output_dir / plot.filename())
