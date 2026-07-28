"""Agente per la generazione della query gold.

:author: Riccardo Morabito
"""

from bench.domain.models.state import TaskStateDTO
from bench.domain.models.sql import GoldQueryDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.ports.outbound.database_port import DatabasePort
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.feature_checker import FeatureChecker
from bench.application.validators.query_validator import QueryValidator
from bench.application.validators.mutation_tester import MutationTester
from bench.application.agents.base import AbstractAgent


class QueryAgent(AbstractAgent):
    """Genera GoldQueryDTO via LLM e la valida eseguendola nel sandbox PostgreSQL."""

    def __init__(self, llm, prompts, config, sandbox: SandboxPort,
                 db: DatabasePort) -> None:
        """Inietta le porte e il validatore query (creato internamente)."""
        super().__init__(llm, prompts, config)
        self._validator = QueryValidator(sandbox, FeatureChecker(), MutationTester(db))

    def prompt_name(self) -> str:
        """Restituisce 'query' come nome del template prompt."""
        return "query"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con schema_ddl, data_inserts e feature_sql."""
        return {
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "data_inserts": state.data_inserts.inserts if state.data_inserts else "",
            "feature_sql": state.spec.sql_features if state.spec else [],
        }

    def output_schema(self) -> type:
        """Restituisce GoldQueryDTO come schema per lo structured output."""
        return GoldQueryDTO

    def validate(self, output: GoldQueryDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida la query via QueryValidator e restituisce gold_result se valida."""
        spec = state.spec or SpecDTO()
        result = self._validator.validate(output, spec, state.sandbox_schema)
        if not result.is_valid:
            return False, result.error, {}
        return True, "", {"gold_result": result.gold_result}

    def build_updates(self, output: GoldQueryDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con gold_query."""
        return {"gold_query": output}