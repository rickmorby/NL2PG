"""Agente per la generazione della narrazione (Story).

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.domain.models.nlp import StoryDTO
from bench.domain.models.state import TaskStateDTO


class StoryAgent(AbstractAgent):
    """Genera StoryDTO via LLM contestualizzando schema, dati e twist."""

    def prompt_name(self) -> str:
        """Restituisce 'story' come nome del template prompt."""
        return "story"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con schema, dati, twist e feedback judge."""
        judge_feedback = ""
        if state.judge_verdict and state.judge_verdict != "hard":
            msg = f"Judge ha valutato la storia precedente come '{state.judge_verdict}'."
            judge_feedback = f"{msg} Migliorala."
        twist_rules = []
        if state.spec and state.spec.twist_rules:
            twist_rules = [r.model_dump() for r in state.spec.twist_rules]
        return {
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "data_inserts": state.data_inserts.inserts if state.data_inserts else "",
            "intent_query": state.gold_query.intent if state.gold_query else "",
            "twist": state.spec.twist if state.spec else [],
            "twist_rules": twist_rules,
            "judge_feedback": judge_feedback,
            "few_shot": self._few_shot(state),
        }

    def output_schema(self) -> type:
        """Restituisce StoryDTO come schema per lo structured output."""
        return StoryDTO

    def build_updates(self, output: StoryDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con story; resetta retry_story se e' un rigenero judge."""
        has_feedback = bool(state.judge_verdict and state.judge_verdict != "hard")
        retry = 0 if has_feedback else state.retry_story + 1
        return {"story": output, "retry_story": retry}

    def _max_retries(self, _state: TaskStateDTO) -> int:
        return 1
