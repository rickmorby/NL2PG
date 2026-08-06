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

from pathlib import Path

from bench.adapters.outbound.config import ConfigAdapter
from bench.adapters.outbound.llm import LLMClientAdapter
from bench.adapters.outbound.logging import LoggingAdapter
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
from bench.application.serializer import BenchmarkSerializer
from bench.application.services.task_runner import TaskRunner
from bench.domain.exceptions import install_global_handler


class ApplicationBootstrap:
    """Composition Root per l'assemblaggio deterministico delle dipendenze.

    Ogni risorsa infrastrutturale (pool DB, client LLM, adattatori I/O)
    viene creata **una sola volta** nel costruttore e condivisa in modo
    thread-safe tra tutti i componenti applicativi.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Inizializza logging, adattatori, agenti, orchestratore e serializzatore."""
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        cfg_dir = config_dir or (base_dir / "config")

        log_adapter = LoggingAdapter(level="DEBUG")
        log_adapter.configure()
        install_global_handler()

        self._config = ConfigAdapter(cfg_dir)
        self._llm = LLMClientAdapter(self._config.load_providers())
        self._pg_client = PostgresClientAdapter(
            config=self._config.load_bench().get("run", {}),
        )
        self._sandbox = PostgresSandboxAdapter(self._pg_client)
        self._meta_repo = MetaRepositoryAdapter(self._pg_client)
        self._prompts = PromptAdapter(base_dir / "prompts")

        agents = self._build_agents()

        self._orchestrator = Orchestrator(
            self._sandbox, self._config, self._meta_repo, agents,
        )
        self._serializer = BenchmarkSerializer()


    def task_runner(self) -> TaskRunner:
        """Restituisce un TaskRunner pronto all'uso per la generazione batch."""
        return TaskRunner(
            self._orchestrator,
            self._meta_repo,
            self._serializer,
            self._config,
        )


    @property
    def config(self) -> ConfigAdapter:
        """Restituisce l'adattatore di configurazione."""
        return self._config

    @property
    def llm(self) -> LLMClientAdapter:
        """Restituisce l'adattatore LLM."""
        return self._llm

    @property
    def pg_client(self) -> PostgresClientAdapter:
        """Restituisce il client PostgreSQL."""
        return self._pg_client


    def close(self) -> None:
        """Rilascia ordinatamente pool DB e client LLM."""
        try:
            self._pg_client.close()
        except Exception:
            pass
        try:
            self._llm.close()
        except Exception:
            pass


    def _build_agents(self) -> dict[str, object]:
        """Assembla il dizionario degli agenti iniettando le dipendenze condivise."""
        llm = self._llm
        prompts = self._prompts
        cfg = self._config
        sandbox = self._sandbox
        meta = self._meta_repo
        pg = self._pg_client

        return {
            "spec": SpecAgent(llm, prompts, cfg, meta),
            "schema": SchemaAgent(llm, prompts, cfg, sandbox),
            "data": DataAgent(llm, prompts, cfg, sandbox),
            "query": QueryAgent(llm, prompts, cfg, sandbox, pg),
            "story": StoryAgent(llm, prompts, cfg),
            "question": QuestionAgent(llm, prompts, cfg),
            "critic": CriticAgent(llm, prompts, cfg),
            "hardening": HardeningAgent(llm, prompts, cfg),
            "calibration": CalibrationAgent(llm, prompts, cfg, sandbox),
            "judge": JudgeAgent(llm, prompts, cfg),
        }
