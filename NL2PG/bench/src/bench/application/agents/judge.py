"""Agente per il giudizio finale (Judge) sulla qualita' del task.

:author: Riccardo Morabito
"""

from bench.domain.models.state import TaskStateDTO
from bench.domain.models.nlp import JudgeDTO
from bench.application.agents.base import AbstractAgent


class JudgeAgent(AbstractAgent):
    """Valuta la qualita' complessiva del task e restituisce un verdetto via LLM."""

    def prompt_name(self) -> str:
        """Restituisce 'judge' come nome del template prompt."""
        return "judge"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con story, question, schema e gold_query."""
        return {
            "story": state.story.story if state.story else "",
            "question": state.question.question if state.question else "",
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "gold_query": state.gold_query.query if state.gold_query else "",
        }

    def output_schema(self) -> type:
        """Restituisce JudgeDTO come schema per lo structured output."""
        return JudgeDTO

    def build_updates(self, output: JudgeDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con verdict e regens."""
        regens = state.judge_regens + (1 if output.verdict != "hard" else 0)
        return {"judge_verdict": output.verdict, "judge_regens": regens}

    def _max_retries(self, _state: TaskStateDTO) -> int:
        return 1