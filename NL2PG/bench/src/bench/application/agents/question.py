"""Agente per la generazione della domanda (Question).

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.domain.models.nlp import QuestionDTO
from bench.domain.models.state import TaskStateDTO


class QuestionAgent(AbstractAgent):
    """Genera QuestionDTO via LLM contestualizzando la storia e la query gold."""

    def prompt_name(self) -> str:
        """Restituisce 'question' come nome del template prompt."""
        return "question"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con story, intent e schema."""
        return {
            "story": state.story.story if state.story else "",
            "intent_query": state.gold_query.intent if state.gold_query else "",
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
        }

    def output_schema(self) -> type:
        """Restituisce QuestionDTO come schema per lo structured output."""
        return QuestionDTO

    def validate(self, output: QuestionDTO, _state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida che il testo della domanda generata sia non vuoto."""
        if not output.question or not output.question.strip():
            return False, "La domanda prodotta dall'LLM e' vuota.", {}
        return True, "", {}

    def build_updates(self, output: QuestionDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con question e incrementa retry_question."""
        return {"question": output, "retry_question": state.retry_question + 1}

    def _max_retries(self, _state: TaskStateDTO) -> int:
        return 1
