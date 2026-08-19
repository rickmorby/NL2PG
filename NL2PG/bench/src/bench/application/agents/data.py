"""Agente per la progettazione della DataSpec e la materializzazione dei dati.

Il Data Agent emette una DataSpecDTO compatta (nature, template canonici e
assi di variazione); il DataMaterializer deterministico (seed derivato dal
task_id) la espande in centinaia/migliaia di righe conformi allo schema, che
vengono eseguite nel sandbox PostgreSQL come autorita' finale (FK, NOT NULL,
CHECK). Gli agenti a valle (query, story, critic) ricevono il profilo dati
deterministico con righe campione reali, non lo script INSERT completo.

:author: Riccardo Morabito
"""

from hashlib import sha1

from bench.application.agents.base import AbstractAgent
from bench.application.validators.data_validator import DataValidator
from bench.domain.models.data import DataProfileDTO, DataSpecDTO
from bench.domain.models.sql import DataInsertsDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.example_port import ExamplePort
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.data_materializer import DataMaterializer

_SEED_HEX_LEN = 8


class DataAgent(AbstractAgent):
    """Genera DataSpecDTO via LLM e materializza/valida i dati nel sandbox PostgreSQL."""

    def __init__(
        self, llm, prompts, config, sandbox: SandboxPort, examples: ExamplePort | None = None
    ) -> None:
        """Inietta le porte, gli esempi, il validatore e il materializer configurato."""
        super().__init__(llm, prompts, config, examples)
        self._validator = DataValidator(sandbox)
        self._sandbox = sandbox
        self._materializer = DataMaterializer(
            nature_ranges=config.data_nature_ranges(),
            max_rows_per_table=config.data_max_rows_per_table(),
            max_total_rows=config.data_max_total_rows(),
            batch_size=config.data_batch_size(),
            null_rate=config.data_null_rate(),
            dup_rate=config.data_dup_rate(),
            outlier_rate=config.data_outlier_rate(),
        )
        self._preview_size = config.data_preview_size()

    def prompt_name(self) -> str:
        """Restituisce 'data' come nome del template prompt."""
        return "data"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con schema_ddl, spec e few-shot."""
        return {
            "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "few_shot": self._few_shot(state),
        }

    def output_schema(self) -> type:
        """Restituisce DataSpecDTO come schema per lo structured output."""
        return DataSpecDTO

    def validate(self, output: DataSpecDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Materializza la spec in modo deterministico e valida i dati nel sandbox."""
        schema_model = self._sandbox.introspect_schema(state.sandbox_schema)
        seed = self.seed_for_task(state.task_id)
        materialized = self._materializer.materialize(output, schema_model, seed)
        inserts = DataInsertsDTO(inserts=materialized.insert_script)
        result = self._validator.validate(inserts, state.sandbox_schema)
        if not result.is_valid:
            return False, result.error, {}
        profile = DataProfileDTO(
            profile=materialized.profile,
            preview={
                table_name: table_rows[: self._preview_size]
                for table_name, table_rows in materialized.rows.items()
            },
        )
        return True, "", {"data_inserts": inserts, "data_profile": profile}

    def build_updates(self, output: DataSpecDTO, _state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con la data_spec prodotta dall'LLM."""
        return {"data_spec": output}

    @staticmethod
    def seed_for_task(task_id: str) -> int:
        """Deriva un seed deterministico e stabile dal task_id."""
        digest = sha1(task_id.encode("utf-8")).hexdigest()
        return int(digest[:_SEED_HEX_LEN], 16)
