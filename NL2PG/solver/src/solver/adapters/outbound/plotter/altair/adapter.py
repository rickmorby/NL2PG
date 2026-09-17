"""Adattatore Altair per la generazione dei grafici scientifici della run.

Sostituisce il motore matplotlib/seaborn con la stessa architettura dichiarativa
del progetto bench: tema registrato, Template Method ``Plot``, export offline
deterministico via vl-convert.

:author: Riccardo Morabito
"""

from logging import getLogger
from pathlib import Path

from solver.adapters.outbound.plotter.altair.base import Plot
from solver.adapters.outbound.plotter.altair.plots import get_default_plots
from solver.domain.exceptions import SolverException
from solver.domain.models.solver import SolverRunDTO
from solver.domain.ports.outbound.plotter_port import PlotterPort

_log = getLogger("solver.adapters.plotter")


class AltairSolverPlotterAdapter(PlotterPort):
    """Adattatore dichiarativo per la suite dei grafici della run del solver."""

    def __init__(self, plots: list[Plot] | None = None) -> None:
        """Inizializza l'adattatore con la suite di default dei 12 grafici."""
        self._plots = plots or get_default_plots()

    def generate_plots(self, run_dto: SolverRunDTO, output_dir: Path) -> list[Path]:
        """Genera PNG @2x e SVG per ogni grafico, isolando i fallimenti singoli."""
        output_dir.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []
        for plot in self._plots:
            stem = output_dir / plot.filename()
            try:
                plot.render(run_dto, stem)
                generated.append(stem.with_suffix(".png"))
            except (SolverException, OSError, ValueError, TypeError, RuntimeError) as exc:
                _log.warning("Generazione grafico '%s' fallita: %s", plot.filename(), exc)
        return generated
