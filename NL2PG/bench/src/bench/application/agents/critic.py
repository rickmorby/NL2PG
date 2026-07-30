"""Agente per la valutazione qualitativa (Critic) della narrazione.

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.domain.models.nlp import CriticScoresDTO
from bench.domain.models.state import TaskStateDTO


class CriticAgent(AbstractAgent):
    """Valuta la qualita' della narrazione generando CriticScoresDTO via LLM."""

    def prompt_name(self) -> str:
        """Restituisce 'critic' come nome del template prompt."""
        return "critic"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con story, question, gold_query e pesi."""
        weights = self._config.load_bench().get("critic", {}).get("weights", {})
        return {
            "story": state.story.story if state.story else "",
            "question": state.question.question if state.question else "",
            "gold_query": state.gold_query.query if state.gold_query else "",
            "w_narrative": weights.get("narrative", 1.0),
            "w_distractors": weights.get("distractors", 1.0),
            "w_plot_twists": weights.get("plot_twists", 1.0),
            "w_jargon": weights.get("jargon", 1.0),
            "w_sql_composition": weights.get("sql_composition", 1.0),
        }

    def output_schema(self) -> type:
        """Restituisce CriticScoresDTO come schema per lo structured output."""
        return CriticScoresDTO

    def validate(self, output: CriticScoresDTO, _state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida che tutti i punteggi numerici rientrino nell'intervallo [1.0, 10.0]."""
        for field in ("narrative", "distractors", "plot_twists", "jargon", "sql_composition"):
            score = getattr(output, field, 0.0)
            if not (1.0 <= score <= 10.0):
                msg = f"Punteggio '{field}' ({score}) fuori dai vincoli [1.0, 10.0]."
                return False, msg, {}
        return True, "", {}

    def build_updates(self, output: CriticScoresDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con critic."""
        return {"critic": output}

    def _max_retries(self, _state: TaskStateDTO) -> int:
        return 1
