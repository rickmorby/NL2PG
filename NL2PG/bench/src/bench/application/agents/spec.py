"""Agente per la generazione della specifica formale (Spec) del task.

:author: Riccardo Morabito
"""

from bench.domain.models.category import CategoryDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.services.domain_pool import DOMAIN_POOL
from bench.domain.services.spec_validation import validate_spec
from bench.application.agents.base import AbstractAgent


class SpecAgent(AbstractAgent):
    """Genera SpecDTO da categoria, validando twist e feature contro il vocabolario."""

    def prompt_name(self) -> str:
        """Restituisce 'spec' come nome del template prompt."""
        return "spec"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con descrizione, feature, twist e domini."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        return {
            "cat_descrizione": cat.descrizione,
            "cat_feature_sql": cat.feature_sql,
            "cat_tipo_schema": cat.tipo_schema,
            "cat_twist": cat.twist_ammessi,
            "cat_vincoli": cat.vincoli,
            "domains": DOMAIN_POOL,
        }

    def output_schema(self) -> type:
        """Restituisce SpecDTO come schema per lo structured output."""
        return SpecDTO

    def validate(self, output: SpecDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida twist e feature SQL contro il vocabolario della categoria ."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        ok, err = validate_spec(output, cat)
        return (ok, err, {})

    def build_updates(self, output: SpecDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con spec."""
        return {"spec": output}