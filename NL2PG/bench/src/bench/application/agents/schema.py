"""Agente per la generazione dello schema DDL.

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.application.validators.schema_validator import SchemaValidator
from bench.domain.models.category import CategoryDTO
from bench.domain.models.sql import SchemaDDLDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.example_port import ExamplePort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort
from bench.domain.services.validation.sql_repair import PostgresSQLRepair


class SchemaAgent(AbstractAgent):
    """Genera SchemaDDLDTO via LLM e lo valida eseguendolo nel sandbox PostgreSQL."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        validator: SchemaValidator,
        examples: ExamplePort | None = None,
    ) -> None:
        """Inietta le porte outbound, gli esempi e il validatore schema."""
        super().__init__(llm, prompts, config, examples)
        self._validator = validator
        self._repair = PostgresSQLRepair()

    def prompt_name(self) -> str:
        """Restituisce 'schema' come nome del template prompt."""
        return "schema"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con tipo schema, descrizione, spec e few-shot."""
        few_shot = self._few_shot(state)
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        return {
            "cat_tipo_schema": cat.tipo_schema,
            "cat_descrizione": cat.descrizione,
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "few_shot": few_shot,
        }

    def output_schema(self) -> type:
        """Restituisce SchemaDDLDTO come schema per lo structured output."""
        return SchemaDDLDTO

    def validate(self, output: SchemaDDLDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida il DDL eseguendolo nel sandbox e verificando tipo e numero di tabelle."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        result = self._validator.validate_with_type(output, state.sandbox_schema, cat.tipo_schema)
        if not result.is_valid:
            return (False, result.error, {})
        expected = state.spec.n_tables if state.spec else 0
        if expected:
            actual = self._validator.table_count(state.sandbox_schema)
            if actual != expected:
                return (False, f"DDL con {actual} tabelle, ma la spec richiede {expected}", {})
        return (True, "", {})

    def build_updates(self, output: SchemaDDLDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con il DDL riparato.

        Il gold deve coincidere con l'SQL effettivamente eseguito dal sandbox (che
        ripara prima di eseguire), altrimenti il solver caricherebbe un DDL diverso
        (es. GENERATED con subquery) e crasherebbe.
        """
        return {"schema_ddl": SchemaDDLDTO(ddl=self._repair.repair(output.ddl))}
