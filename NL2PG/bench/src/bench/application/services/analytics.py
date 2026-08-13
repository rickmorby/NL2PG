"""Servizio applicativo facade per la generazione di metriche ed orchestrazione grafica.

:author: Riccardo Morabito
"""

from logging import getLogger
from pathlib import Path
from typing import Any

from bench.domain.models.analytics import AnalyticsDTO
from bench.domain.ports.inbound.analytics_port import AnalyticsServicePort
from bench.domain.ports.outbound.plotter_port import PlotterPort
from bench.domain.ports.outbound.serializer_port import BenchmarkSerializerPort
from bench.domain.services.analytics_calculator import AnalyticsCalculator

_log = getLogger("bench.application.analytics")


class BenchmarkAnalyticsService(AnalyticsServicePort):
    """Servizio applicativo facade che coordina dominio, serializzatore e porta grafica."""

    def __init__(
        self,
        serializer: BenchmarkSerializerPort,
        plotter: PlotterPort,
        calculator: AnalyticsCalculator | None = None,
    ) -> None:
        """Inietta il serializzatore, la porta del plotter ed il calcolatore di dominio."""
        self._serializer = serializer
        self._plotter = plotter
        self._calculator = calculator or AnalyticsCalculator()

    def generate_analytics(self, target_path: Path) -> AnalyticsDTO:
        """Coordina la lettura dei task, il calcolo delle metriche ed il salvataggio dei grafici."""
        tasks, run_id, plots_dir = self._resolve_paths(target_path)
        if not tasks:
            _log.warning("Nessun task trovato in '%s'. Analytics non generate.", target_path)
            return AnalyticsDTO()

        plots_dir.mkdir(parents=True, exist_ok=True)
        analytics = self._calculator.compute_metrics(tasks, run_id)
        self._serializer.write_single_task(analytics.model_dump(), plots_dir / "analytics.json")
        for stale in plots_dir.glob("*.png"):
            stale.unlink()
        self._plotter.render_plots(tasks, plots_dir)
        analytics.plots_count = len(list(plots_dir.glob("*.png")))

        _log.info(
            "Analytics e %d grafici scientifici generati in '%s'.",
            analytics.plots_count,
            plots_dir,
        )
        return analytics

    def _resolve_paths(self, target_path: Path) -> tuple[list[dict[str, Any]], str, Path]:
        """Carica il file JSON di run e determina la directory output/plots/run_<name>/."""
        p = target_path.resolve()
        output_dir = next(
            (parent for parent in (p, *p.parents) if parent.name == "output"), p.parent
        )

        json_file = target_path
        if target_path.is_dir():
            files = sorted(
                list(target_path.glob("benchmarks/*.json"))
                + list(target_path.glob("run_*.json"))
                + list(target_path.rglob("benchmark_samples.json"))
            )
            if files:
                json_file = files[-1]
        elif not json_file.exists():
            search_dir = output_dir / "benchmarks"
            if search_dir.is_dir():
                matches = sorted(list(search_dir.glob(f"*{target_path.name}*")))
                if matches:
                    json_file = matches[-1]

        if not json_file.is_file():
            return [], "", output_dir / "plots" / "run_unknown"

        doc = self._serializer.read(json_file)
        tasks = doc.get("tasks", [])
        run_id = doc.get("run_id", "unknown")
        is_samples = json_file.name == "benchmark_samples.json"
        run_name = json_file.stem if not is_samples else f"run_{run_id}"

        plots_dir = output_dir / "plots" / run_name
        return tasks, run_id, plots_dir
