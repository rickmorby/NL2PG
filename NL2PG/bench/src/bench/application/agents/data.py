"""Agente per la generazione dei dati INSERT.

:author: Riccardo Morabito
"""

from bench.domain.models.state import TaskStateDTO
from bench.domain.models.sql import DataInsertsDTO
from bench.domain.ports.outbound.example_port import ExamplePort
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.application.validators.data_validator import DataValidator
from bench.application.agents.base import AbstractAgent


class DataAgent(AbstractAgent):
    """Genera DataInsertsDTO via LLM e li valida eseguendoli nel sandbox PostgreSQL."""

    def __init__(
        self, llm, prompts, config, sandbox: SandboxPort, examples: ExamplePort | None = None
    ) -> None:
        """Inietta le porte, gli esempi e il validatore dati (creato internamente)."""
        super().__init__(llm, prompts, config, examples)
        self._validator = DataValidator(sandbox)

    def prompt_name(self) -> str:
        """Restituisce 'data' come nome del template prompt."""
        return "data"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con schema_ddl e spec."""
        return {
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "few_shot": self._few_shot(state),
        }

    def output_schema(self) -> type:
        """Restituisce DataInsertsDTO come schema per lo structured output."""
        return DataInsertsDTO

    def validate(self, output: DataInsertsDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida le INSERT eseguendole nel sandbox via DataValidator."""
        result = self._validator.validate(output, state.sandbox_schema)
        return (result.is_valid, result.error, {})

    def build_updates(self, output: DataInsertsDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con data_inserts."""
        return {"data_inserts": output}
