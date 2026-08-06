"""Agente per la generazione dello schema DDL.

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.application.validators.schema_validator import SchemaValidator
from bench.domain.models.category import CategoryDTO
from bench.domain.models.sql import SchemaDDLDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort


class SchemaAgent(AbstractAgent):
    """Genera SchemaDDLDTO via LLM e lo valida eseguendolo nel sandbox PostgreSQL."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        validator: SchemaValidator,
    ) -> None:
        """Inietta le porte outbound e il validatore schema."""
        super().__init__(llm, prompts, config)
        self._validator = validator

    def prompt_name(self) -> str:
        """Restituisce 'schema' come nome del template prompt."""
        return "schema"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con descrizione categoria, spec e few-shot."""
        few_shot = self._prompts.few_shot(state.category)
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        return {
            "cat_descrizione": cat.descrizione,
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "few_shot": few_shot,
        }

    def output_schema(self) -> type:
        """Restituisce SchemaDDLDTO come schema per lo structured output."""
        return SchemaDDLDTO

    def validate(self, output: SchemaDDLDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida il DDL eseguendolo nel sandbox via SchemaValidator."""
        result = self._validator.validate(output, state.sandbox_schema)
        return (result.is_valid, result.error, {})

    def build_updates(self, output: SchemaDDLDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con schema_ddl."""
        return {"schema_ddl": output}
