"""Servizio applicativo per il calcolo delle statistiche e generazione grafici del solver.

:author: Riccardo Morabito
"""

from logging import getLogger
from pathlib import Path

from orjson import OPT_INDENT_2, dumps as orjson_dumps

from solver.domain.models.analytics import SolverAnalyticsDTO
from solver.domain.models.solver import SolverRunDTO
from solver.domain.ports.inbound.analytics_port import SolverAnalyticsPort
from solver.domain.ports.outbound.plotter_port import PlotterPort
from solver.domain.ports.outbound.serializer_port import SerializerPort
from solver.domain.services.analytics_calculator import SolverAnalyticsCalculator

_log = getLogger("solver.application.analytics")


class SolverAnalyticsService(SolverAnalyticsPort):
    """Servizio per l'analisi scientifica dei risultati di risoluzione e generazione grafici PNG."""

    def __init__(
        self,
        serializer: SerializerPort,
        plotter: PlotterPort,
        calculator: SolverAnalyticsCalculator | None = None,
    ) -> None:
        """Inietta le porte per caricamento, rendering ed il calcolatore di dominio."""
        self._serializer = serializer
        self._plotter = plotter
        self._calculator = calculator or SolverAnalyticsCalculator()

    def analyze_run(self, run_json_path: Path, output_plots_dir: Path) -> list[Path]:
        """Carica un file JSON di run, genera analytics.json e la suite di 14 grafici PNG."""
        run_dto: SolverRunDTO = self._serializer.load_run(run_json_path)
        output_plots_dir.mkdir(parents=True, exist_ok=True)

        analytics_dto: SolverAnalyticsDTO = self._calculator.compute_analytics(run_dto)

        plots = self._plotter.generate_plots(run_dto, output_plots_dir)
        analytics_dto.plots_count = len(plots)

        analytics_file = output_plots_dir / "analytics.json"
        tmp_file = analytics_file.with_suffix(".tmp")
        payload = orjson_dumps(analytics_dto.model_dump(mode="json"), option=OPT_INDENT_2)
        tmp_file.write_bytes(payload)
        tmp_file.replace(analytics_file)

        _log.info(
            "Analytics scientifiche e %d grafici salvati in '%s'.",
            len(plots),
            output_plots_dir,
        )
        return plots
