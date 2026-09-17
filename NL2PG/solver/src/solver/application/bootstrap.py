"""Composition Root dell'applicazione Solver.

Inizializza gli adattatori di infrastruttura, inietta le dipendenze nei servizi
di dominio ed applicativi, e gestisce il ciclo di vita dell'applicazione.

:author: Riccardo Morabito
"""

from logging import getLogger
from pathlib import Path

from solver.adapters.outbound.config import ConfigAdapter
from solver.adapters.outbound.datalog.clingo_adapter import ClingoDatalogAdapter
from solver.adapters.outbound.llm.llm_adapter import LLMClientAdapter
from solver.adapters.outbound.logging import LoggingAdapter
from solver.adapters.outbound.plotter.altair import AltairSolverPlotterAdapter
from solver.adapters.outbound.postgres.database_adapter import PostgresClientAdapter
from solver.adapters.outbound.postgres.sandbox_adapter import PostgresSandboxAdapter
from solver.adapters.outbound.prompts import PromptAdapter
from solver.adapters.outbound.rag.doc_rag_adapter import DocRAGAdapter
from solver.adapters.outbound.serializer.json_serializer_adapter import JsonSerializerAdapter
from solver.application.services.analytics import SolverAnalyticsService
from solver.application.services.solver_runner import SolverRunnerService
from solver.domain.exceptions import install_global_handler
from solver.domain.ports.inbound.analytics_port import SolverAnalyticsPort
from solver.domain.ports.inbound.solver_runner_port import SolverRunnerPort

_log = getLogger("solver.application.bootstrap")


class ApplicationBootstrap:
    """Composition Root dell'applicazione solver."""

    def __init__(self, config_dir: Path | None = None, base_dir: Path | None = None) -> None:
        """Inizializza la Composition Root individuando i percorsi dell'applicazione."""
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent.parent
        self.config_dir = config_dir or (self.base_dir / "config")

        log_adapter = LoggingAdapter(level="DEBUG")
        log_adapter.configure()
        install_global_handler()

        self._config_adapter = ConfigAdapter(self.config_dir)

        self._db_client = PostgresClientAdapter(sandbox_dsn=self._config_adapter.dsn("sandbox_dsn"))
        self._sandbox_adapter = PostgresSandboxAdapter(self._db_client)

        self._datalog_adapter = ClingoDatalogAdapter()

        rag_path = self._config_adapter.load_rag_dir()
        self._rag_adapter = DocRAGAdapter(
            qdrant_url=self._config_adapter.qdrant_url(),
            collection_name=self._config_adapter.rag_collection_name(),
            embedding_model=self._config_adapter.embedding_model(),
            rag_dir=rag_path,
        )

        providers_cfg = self._config_adapter.load_providers()
        self._llm_adapter = LLMClientAdapter(config=providers_cfg)

        self._serializer_adapter = JsonSerializerAdapter()
        self._plotter_adapter = AltairSolverPlotterAdapter()

        self._prompt_adapter = PromptAdapter(self.base_dir / "prompts")

        self._analytics_service = SolverAnalyticsService(
            serializer=self._serializer_adapter,
            plotter=self._plotter_adapter,
        )

        self._solver_runner_service = SolverRunnerService(
            config=self._config_adapter,
            llm=self._llm_adapter,
            sandbox=self._sandbox_adapter,
            datalog=self._datalog_adapter,
            rag=self._rag_adapter,
            serializer=self._serializer_adapter,
            analytics=self._analytics_service,
            prompts=self._prompt_adapter,
        )

    def solver_runner(self) -> SolverRunnerPort:
        """Restituisce la porta primaria SolverRunnerPort per l'esecuzione batch."""
        return self._solver_runner_service

    def analytics(self) -> SolverAnalyticsPort:
        """Restituisce la porta primaria SolverAnalyticsPort per analytics e grafici."""
        return self._analytics_service

    def default_benchmark_path(self) -> Path | None:
        """Restituisce il percorso di default per i benchmark configurato in solver.toml."""
        return self._config_adapter.default_benchmark_path()

    def __enter__(self) -> "ApplicationBootstrap":
        """Consente l'utilizzo di ApplicationBootstrap come context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Garantisce il rilascio controllato delle risorse allo scadere del contesto."""
        self.close()

    def close(self) -> None:
        """Chiude le connessioni ed i client dell'applicazione."""
        if hasattr(self, "_db_client"):
            self._db_client.close()
        _log.info("Risorse dell'applicazione Solver liberate correttamente.")
