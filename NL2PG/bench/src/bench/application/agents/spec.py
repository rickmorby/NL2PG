"""Agente per la generazione della specifica formale (Spec) del task.

:author: Riccardo Morabito
"""

import random
from hashlib import sha1

from bench.application.agents.base import AbstractAgent
from bench.domain.models.category import CategoryDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.example_port import ExamplePort
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
        examples: ExamplePort | None = None,
    ) -> None:
        """Inietta le porte per LLM, prompt, configurazione, esempi e repository metadati."""
        super().__init__(llm, prompts, config, examples)
        self._meta_repo = meta_repo

    def prompt_name(self) -> str:
        """Restituisce 'spec' come nome del template prompt."""
        return "spec"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con descrizione, feature, twist e domini."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        lo, hi = cat.n_tables_range
        target = self._target_n_tables(state.task_id, state.category, cat.n_tables_range)
        return {
            "cat_descrizione": cat.descrizione,
            "cat_feature_sql": cat.feature_sql,
            "cat_tipo_schema": cat.tipo_schema,
            "cat_twist": cat.twist_ammessi,
            "cat_vincoli": cat.vincoli,
            "domains": DOMAIN_POOL,
            "target_domain": state.target_domain,
            "n_tables_range": f"{lo}-{hi}",
            "target_n_tables": target,
            "few_shot": self._few_shot(state),
        }

    @staticmethod
    def _target_n_tables(task_id: str, category: str, table_range: list[int]) -> int:
        """Deriva deterministicamente il numero di tabelle dal task_id entro il range."""
        lo, hi = table_range
        digest = sha1(f"{task_id}:{category}".encode("utf-8")).hexdigest()
        return random.Random(int(digest[:8], 16)).randint(lo, hi)

    def output_schema(self) -> type:
        """Restituisce SpecDTO come schema per lo structured output."""
        return SpecDTO

    def validate(self, output: SpecDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida vocabolario categoria, target_domain e assenza di duplicati via spec_hash."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        target = self._target_n_tables(state.task_id, state.category, cat.n_tables_range)
        ok, err = validate_spec(
            output, cat, target_domain=state.target_domain, target_n_tables=target
        )
        if not ok:
            return False, err, {}

        spec_hash = compute_spec_hash(state.category, output)
        output.spec_hash = spec_hash

        if self._meta_repo.is_spec_duplicated(state.category, spec_hash):
            msg = (
                f"Specifica duplicata per la categoria '{state.category}' (hash={spec_hash}). "
                "Genera una specifica con dominio, numero di tabelle, feature SQL o twist diversi."
            )
            return False, msg, {}

        return True, "", {}

    def build_updates(self, output: SpecDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con spec e target_n_tables deterministico."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        target = self._target_n_tables(state.task_id, state.category, cat.n_tables_range)
        return {"spec": output, "target_n_tables": target}
