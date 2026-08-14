"""Composition Root per la Dependency Injection nativa del benchmark.

Modulo responsabile dell'assemblaggio deterministico di tutte le dipendenze
dell'applicazione. Ogni adattatore infrastrutturale viene istanziato una sola
volta e condiviso tra tutti i componenti che ne necessitano.

Sicurezza concorrente: psycopg_pool.ConnectionPool e litellm.Router sono
thread-safe per design. ConfigAdapter e PromptAdapter sono stateless.
Orchestrator compila il grafo per ogni task con MemorySaver dedicato.
TaskRunner e' protetto da threading.Lock per la scrittura parallela.

:author: Riccardo Morabito
"""

from contextlib import suppress
from pathlib import Path

from bench.adapters.outbound.config import ConfigAdapter
from bench.adapters.outbound.examples import ExampleAdapter
from bench.adapters.outbound.llm import LLMClientAdapter
from bench.adapters.outbound.logging import LoggingAdapter
from bench.adapters.outbound.plotter.seaborn_adapter import SeabornPlotterAdapter
from bench.adapters.outbound.postgres import (
    MetaRepositoryAdapter,
    PostgresClientAdapter,
    PostgresSandboxAdapter,
)
from bench.adapters.outbound.prompts import PromptAdapter
from bench.application.agents import (
    CalibrationAgent,
    CriticAgent,
    DataAgent,
    HardeningAgent,
    JudgeAgent,
    QueryAgent,
    QuestionAgent,
    SchemaAgent,
    SpecAgent,
    StoryAgent,
)
from bench.application.orchestrator import Orchestrator
from bench.adapters.outbound.serializer import JsonBenchmarkSerializerAdapter
from bench.application.services.analytics import BenchmarkAnalyticsService
from bench.application.services.database_cleaner import DatabaseCleanupService
from bench.application.services.system_checker import SystemCheckService
from bench.application.services.task_promoter import TaskPromoterService
from bench.application.services.task_runner import TaskRunner
from bench.application.validators.mutation_tester import MutationTester
from bench.application.validators.query_validator import QueryValidator
from bench.application.validators.schema_validator import SchemaValidator
from bench.domain.exceptions import install_global_handler
from bench.domain.ports.inbound import (
    AnalyticsServicePort,
    DatabaseCleanerPort,
    SystemCheckPort,
    TaskPromoterPort,
    TaskRunnerPort,
)
from bench.domain.services.feature_checker import FeatureChecker
from bench.domain.services.role_example_builder import RoleExampleBuilder


class ApplicationBootstrap:
    """Composition Root per l'assemblaggio deterministico delle dipendenze.

    Ogni risorsa infrastrutturale (pool DB, client LLM, adattatori I/O)
    viene creata **una sola volta** nel costruttore e condivisa in modo
    thread-safe tra tutti i componenti applicativi.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Inizializza logging, adattatori, agenti, orchestratore e serializzatore."""
        self._base_dir = Path(__file__).resolve().parent.parent.parent.parent
        cfg_dir = config_dir or (self._base_dir / "config")

        log_adapter = LoggingAdapter(level="DEBUG")
        log_adapter.configure()
        install_global_handler()

        self._config = ConfigAdapter(cfg_dir)
        self._llm = LLMClientAdapter(self._config.load_providers())
        self._pg_client = PostgresClientAdapter(
            sandbox_dsn=self._config.dsn("sandbox_dsn"),
            meta_dsn=self._config.dsn("meta_dsn"),
        )
        self._sandbox = PostgresSandboxAdapter(self._pg_client)
        self._meta_repo = MetaRepositoryAdapter(self._pg_client)
        self._prompts = PromptAdapter(self._base_dir / "prompts")
        self._examples = ExampleAdapter(self._base_dir / "examples")
        self._role_example_builder = RoleExampleBuilder()

        schema_validator = SchemaValidator(self._sandbox)
        mutation_tester = MutationTester(self._sandbox)
        query_validator = QueryValidator(self._sandbox, FeatureChecker(), mutation_tester)

        agents = self._build_agents(schema_validator, query_validator)

        self._orchestrator = Orchestrator(
            self._sandbox,
            self._config,
            self._meta_repo,
            agents,
        )
        self._serializer = JsonBenchmarkSerializerAdapter()
        self._plotter = SeabornPlotterAdapter()
        self._analytics = BenchmarkAnalyticsService(self._serializer, self._plotter)

    @property
    def base_dir(self) -> Path:
        """Restituisce il percorso della directory radice del progetto bench."""
        return self._base_dir

    def task_runner(self) -> TaskRunnerPort:
        """Restituisce la porta astratta TaskRunnerPort per la generazione batch dei task."""
        return TaskRunner(
            self._orchestrator,
            self._meta_repo,
            self._serializer,
            self._config,
            analytics=self._analytics,
        )

    def task_promoter(self) -> TaskPromoterPort:
        """Restituisce la porta astratta TaskPromoterPort per la promozione dei task accettati."""
        return TaskPromoterService(self._serializer, self._role_example_builder)

    def database_cleaner(self) -> DatabaseCleanerPort:
        """Restituisce la porta astratta DatabaseCleanerPort per la pulizia degli schemi orfani."""
        return DatabaseCleanupService(self._sandbox)

    def system_checker(self) -> SystemCheckPort:
        """Restituisce la porta astratta SystemCheckPort per la diagnosi ed i controlli."""
        return SystemCheckService(self._config, self._llm)

    def analytics(self) -> AnalyticsServicePort:
        """Restituisce la porta astratta AnalyticsServicePort per la visualizzazione ed analisi."""
        return self._analytics

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
        """Rilascia ordinatamente pool DB e client LLM."""
        with suppress(Exception):
            self._pg_client.close()
        with suppress(Exception):
            self._llm.close()

    def _build_agents(
        self, schema_validator: SchemaValidator, query_validator: QueryValidator
    ) -> dict[str, object]:
        """Assembla il dizionario degli agenti iniettando le dipendenze condivise."""
        llm = self._llm
        prompts = self._prompts
        cfg = self._config
        sandbox = self._sandbox
        meta = self._meta_repo
        examples = self._examples

        return {
            "spec": SpecAgent(llm, prompts, cfg, meta, examples),
            "schema": SchemaAgent(llm, prompts, cfg, schema_validator, examples),
            "data": DataAgent(llm, prompts, cfg, sandbox, examples),
            "query": QueryAgent(llm, prompts, cfg, query_validator, examples),
            "story": StoryAgent(llm, prompts, cfg, examples),
            "question": QuestionAgent(llm, prompts, cfg, examples),
            "critic": CriticAgent(llm, prompts, cfg),
            "hardening": HardeningAgent(llm, prompts, cfg),
            "calibration": CalibrationAgent(llm, prompts, cfg, sandbox),
            "judge": JudgeAgent(llm, prompts, cfg),
        }
