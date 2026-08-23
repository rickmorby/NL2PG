"""Agente per la generazione della domanda (Question).

:author: Riccardo Morabito
"""

from logging import getLogger

from bench.application.agents.base import AbstractAgent
from bench.domain.models.nlp import QuestionDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.services.validation.order_sensitivity_policy import (
    resolve_order_sensitive,
)

_log = getLogger("bench.application.agents")


class QuestionAgent(AbstractAgent):
    """Genera QuestionDTO via LLM contestualizzando la storia e la query gold."""

    def prompt_name(self) -> str:
        """Restituisce 'question' come nome del template prompt."""
        return "question"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con story, intent_query e gold_query."""
        return {
            "story": state.story.story if state.story else "",
            "intent_query": state.gold_query.intent if state.gold_query else "",
            "gold_query": state.gold_query.query if state.gold_query else "",
            "few_shot": self._few_shot(state),
        }

    def output_schema(self) -> type:
        """Restituisce QuestionDTO come schema per lo structured output."""
        return QuestionDTO

    def build_updates(self, output: QuestionDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con question, retry e policy di coerenza order_sensitive."""
        updates: dict = {"question": output, "retry_question": state.retry_question + 1}
        if state.gold_query and state.gold_result:
            resolved, reason = resolve_order_sensitive(
                output.question,
                state.gold_query.query,
                state.gold_result.order_sensitive,
            )
            if reason:
                _log.warning("nodo=question task=%s %s", state.task_id, reason)
                updates["gold_query"] = state.gold_query.model_copy(
                    update={"order_sensitive": resolved}
                )
                updates["gold_result"] = state.gold_result.model_copy(
                    update={"order_sensitive": resolved}
                )
        return updates
