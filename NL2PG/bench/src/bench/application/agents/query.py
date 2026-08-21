"""Agente per la generazione della query gold.

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.application.validators.query_validator import QueryValidator
from bench.domain.models.spec import SpecDTO
from bench.domain.models.sql import GoldQueryDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.example_port import ExamplePort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort


class QueryAgent(AbstractAgent):
    """Genera GoldQueryDTO via LLM e la valida eseguendola nel sandbox PostgreSQL."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        validator: QueryValidator,
        examples: ExamplePort | None = None,
    ) -> None:
        """Inietta le porte outbound, gli esempi e il validatore query."""
        super().__init__(llm, prompts, config, examples)
        self._validator = validator

    def prompt_name(self) -> str:
        """Restituisce 'query' come nome del template prompt."""
        return "query"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con schema_ddl, data_profile e feature_sql."""
        return {
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "data_profile": state.data_profile.model_dump_json() if state.data_profile else "{}",
            "feature_sql": state.spec.sql_features if state.spec else [],
            "few_shot": self._few_shot(state),
        }

    def output_schema(self) -> type:
        """Restituisce GoldQueryDTO come schema per lo structured output."""
        return GoldQueryDTO

    def validate(self, output: GoldQueryDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida la query via QueryValidator e restituisce gold_result se valida."""
        spec = state.spec or SpecDTO()
        result = self._validator.validate(output, spec, state.sandbox_schema, state.data_profile)
        if not result.is_valid:
            return False, result.error, {}
        return True, "", {"gold_result": result.gold_result}

    def build_updates(self, output: GoldQueryDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con gold_query."""
        return {"gold_query": output}
