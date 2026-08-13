"""Agente per la calibrazione (Calibration) della query gold.

:author: Riccardo Morabito
"""

from collections import Counter

from psycopg.errors import Error as PgError
from pydantic import ValidationError
from sqlglot.errors import ParseError

from bench.application.agents.base import AbstractAgent
from bench.domain.exceptions import LLMClientError, ModelOutputContractError
from bench.domain.models.llm import CallOptionsDTO
from bench.domain.models.nlp import CalibrationResultDTO
from bench.domain.models.sql import GoldResultDTO, SolverOutputDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.sql_repair import PostgresSQLRepair


class CalibrationAgent(AbstractAgent):
    """Esegue N run del solver LLM su storia+domanda e calcola il pass_rate."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        sandbox: SandboxPort,
    ) -> None:
        """Inietta le porte, la sandbox e il servizio di riparazione SQL per i tentativi."""
        super().__init__(llm, prompts, config)
        self._sandbox = sandbox
        self._repair = PostgresSQLRepair()

    def prompt_name(self) -> str:
        """Restituisce 'calibration_solver' come nome del template prompt."""
        return "calibration_solver"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con schema_ddl, story e question."""
        return {
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "story": state.story.story if state.story else "",
            "question": state.question.question if state.question else "",
        }

    def output_schema(self) -> type:
        """Restituisce SolverOutputDTO come schema per lo structured output."""
        return SolverOutputDTO

    def build_updates(self, _output: object, _state: TaskStateDTO) -> dict:
        """Non usato: CalibrationAgent override run() completamente."""
        return {}

    def run(self, state: TaskStateDTO, chain_role: str = "calibration") -> dict:
        """Esegue N run del solver LLM con temperatura variabile e calcola il pass_rate."""
        bench_cfg = self._config.load_bench()
        max_runs = bench_cfg.get("calibration", {}).get("runs", 3)
        temp = bench_cfg.get("calibration", {}).get("temperature", 0.9)
        passes = 0
        first_pass = None
        last_model = ""
        for i in range(1, max_runs + 1):
            try:
                prompt = self._prompts.load(self.prompt_name(), **self.build_kwargs(state))
                opts = CallOptionsDTO(temperature_override=temp)
                result = self._llm.call_model(chain_role, prompt, self.output_schema(), opts)
                last_model = result.model_used
                if self._matches_gold(state.sandbox_schema, result.output.query, state.gold_result):
                    passes += 1
                    if first_pass is None:
                        first_pass = i
                        break
            except (PgError, ParseError, ModelOutputContractError, LLMClientError, ValidationError):
                pass
        rate = passes / max_runs
        cal = CalibrationResultDTO(
            pass_rate=rate,
            passes=passes,
            runs=max_runs,
            first_pass_attempt=first_pass,
            model=last_model,
        )
        return {"calibration": cal}

    def _matches_gold(self, schema: str, candidate: str, gold: GoldResultDTO | None) -> bool:
        """Esegue la query candidata (applicando sql_repair) e confronta con il gold."""
        if not gold:
            return False
        try:
            _, rows = self._sandbox.run_query(schema, candidate)
        except Exception:
            repaired_sql = self._repair.repair(candidate)
            if repaired_sql != candidate:
                try:
                    _, rows = self._sandbox.run_query(schema, repaired_sql)
                except Exception:
                    return False
            else:
                return False

        rows = [list(row) for row in rows]
        if gold.order_sensitive:
            return rows == gold.rows
        return Counter(map(tuple, rows)) == Counter(map(tuple, gold.rows))
