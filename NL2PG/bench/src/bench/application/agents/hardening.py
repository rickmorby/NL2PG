"""Agente per il miglioramento iterativo (Hardening) della narrazione.

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.domain.models.nlp import StoryDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.services.validation.coverage_validator import CoverageValidator
from bench.domain.services.validation.narrative_repair import NarrativeRepair


class HardeningAgent(AbstractAgent):
    """Migliora la storia via LLM finche' supera la copertura o raggiunge il max round."""

    def __init__(self, llm, prompts, config) -> None:
        """Inietta le porte, il validatore di copertura e il riparatore narrativo."""
        super().__init__(llm, prompts, config)
        self._coverage = CoverageValidator()
        self._repair = NarrativeRepair()

    def prompt_name(self) -> str:
        """Restituisce 'hardening' come nome del template prompt."""
        return "hardening"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con spec, schema, query, storia e punteggi critic."""
        return {
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "gold_query": state.gold_query.query if state.gold_query else "",
            "story": state.story.story if state.story else "",
            "critic_scores": state.critic.model_dump_json() if state.critic else "{}",
        }

    def output_schema(self) -> type:
        """Restituisce StoryDTO come schema per lo structured output."""
        return StoryDTO

    def validate(self, output: StoryDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida la copertura della nuova storia (sanificata) via CoverageValidator."""
        if not state.spec or not state.gold_query or not state.question:
            return False, "stato incompleto (mancano spec, gold_query o question)", {}
        clean_story = self._repair.repair_story(output.story)
        cleaned_output = StoryDTO(story=clean_story)
        result = self._coverage.validate(
            cleaned_output,
            state.question,
            state.gold_query,
            state.spec,
        )
        return (result.is_valid, result.error, {})

    def build_updates(self, output: StoryDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con story sanificata e incrementa retry_hardening."""
        clean_story = self._repair.repair_story(output.story)
        return {"story": StoryDTO(story=clean_story), "retry_hardening": state.retry_hardening + 1}

    def run(self, state: TaskStateDTO, chain_role: str = "default") -> dict:
        """Esegue il retry loop solo se non ha superato max_rounds."""
        max_rounds = self._config.hardening_max_rounds()
        if state.retry_hardening >= max_rounds:
            return {
                "verdict": "scrapped",
                "last_error": "max hardening rounds",
                "retry_hardening": state.retry_hardening,
            }
        return super().run(state, chain_role)
