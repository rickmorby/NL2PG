"""Agente per la valutazione qualitativa (Critic) della narrazione.

:author: Riccardo Morabito
"""

from typing import Any

from bench.application.agents.base import AbstractAgent
from bench.domain.models.nlp import CriticScoresDTO
from bench.domain.models.state import TaskStateDTO


class CriticAgent(AbstractAgent):
    """Valuta la qualita' della narrazione generando CriticScoresDTO via LLM."""

    def prompt_name(self) -> str:
        """Restituisce 'critic' come nome del template prompt."""
        return "critic"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con spec, schema, dati, query, storia e domanda."""
        return {
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "data_inserts": state.data_inserts.inserts if state.data_inserts else "",
            "gold_query": state.gold_query.query if state.gold_query else "",
            "story": state.story.story if state.story else "",
            "question": state.question.question if state.question else "",
        }

    def output_schema(self) -> type:
        """Restituisce CriticScoresDTO come schema per lo structured output."""
        return CriticScoresDTO

    def validate(self, _output: Any, _state: TaskStateDTO) -> tuple[bool, str, dict]:
        """I vincoli sui punteggi [1.0, 10.0] sono validati nativamente dal DTO CriticScoresDTO."""
        return True, "", {}

    def build_updates(self, output: CriticScoresDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con critic."""
        return {"critic": output}

    def _max_retries(self, _state: TaskStateDTO) -> int:
        return 1
