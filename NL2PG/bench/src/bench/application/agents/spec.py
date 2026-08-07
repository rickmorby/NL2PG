"""Agente per la generazione della specifica formale (Spec) del task.

:author: Riccardo Morabito
"""

from bench.application.agents.base import AbstractAgent
from bench.domain.exceptions import SpecDuplicatedError, handle_exception
from bench.domain.models.category import CategoryDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort
from bench.domain.ports.outbound.repository_port import MetaRepositoryPort
from bench.domain.services.domain_pool import DOMAIN_POOL
from bench.domain.services.spec_validation import compute_spec_hash, validate_spec


class SpecAgent(AbstractAgent):
    """Genera SpecDTO da categoria, validando twist, feature e deduplicazione via repository."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        meta_repo: MetaRepositoryPort,
    ) -> None:
        """Inietta le porte per LLM, prompt, configurazione e repository metadati."""
        super().__init__(llm, prompts, config)
        self._meta_repo = meta_repo

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
            "target_domain": state.target_domain,
        }

    def output_schema(self) -> type:
        """Restituisce SpecDTO come schema per lo structured output."""
        return SpecDTO

    def validate(self, output: SpecDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida vocabolario categoria, target_domain e assenza di duplicati via spec_hash."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        ok, err = validate_spec(output, cat, target_domain=state.target_domain)
        if not ok:
            return False, err, {}

        spec_hash = compute_spec_hash(state.category, output)
        output.spec_hash = spec_hash

        if self._meta_repo.is_spec_duplicated(state.category, spec_hash):
            msg = (
                f"Specifica duplicata per la categoria '{state.category}' (hash={spec_hash}). "
                "Genera una specifica con un dominio, feature SQL o regole twist differenti."
            )
            exc = SpecDuplicatedError(
                msg, payload={"category": state.category, "spec_hash": spec_hash}
            )
            handle_exception(exc)
            return False, msg, {}

        return True, "", {}

    def build_updates(self, output: SpecDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con spec."""
        return {"spec": output}
