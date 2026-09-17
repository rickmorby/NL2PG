"""Builder rigoroso dello stato di lavorazione a partire dal task del benchmark.

Non applica alcun fallback sul formato storico: un task non conforme al contratto
corrente solleva :class:`BenchmarkFormatError`. Il flag ``order_sensitive`` viene
sanitizzato con la policy D1/D2 prima dell'uso.

:author: Riccardo Morabito
"""

from typing import Any

from pydantic import ValidationError

from solver.domain.exceptions import BenchmarkFormatError
from solver.domain.models.state import SolverTaskStateDTO
from solver.domain.models.task import TaskDTO
from solver.domain.services.validation.order_sensitivity_policy import resolve_order_sensitive


class TaskStateBuilder:
    """Costruisce :class:`SolverTaskStateDTO` validando il contratto del benchmark."""

    def build(self, tdata: dict[str, Any]) -> SolverTaskStateDTO:
        """Valida il task grezzo e restituisce lo stato di lavorazione completo."""
        if not isinstance(tdata, dict):
            raise BenchmarkFormatError("Il task non e' un oggetto JSON valido.")

        try:
            task = TaskDTO.model_validate(tdata)
        except ValidationError as exc:
            task_id = tdata.get("task_id", "?") if isinstance(tdata, dict) else "?"
            raise BenchmarkFormatError(f"Task '{task_id}' non conforme: {exc}") from exc

        self._require(task.task_id, "task_id")
        self._require(task.gold.schema_ddl, "gold.schema_ddl")
        self._require(task.gold.data_inserts, "gold.data_inserts")
        self._require(task.gold.query, "gold.query")

        flag, _ = resolve_order_sensitive(
            task.question, task.gold.query, task.gold.result.order_sensitive
        )

        return SolverTaskStateDTO(
            task_id=task.task_id,
            category=task.category,
            domain=task.spec.domain,
            n_tables=task.spec.n_tables,
            hierarchy=task.spec.hierarchy,
            spec_hash=task.spec.spec_hash,
            sql_features=list(task.spec.sql_features),
            twists=list(task.spec.twist),
            twist_rules=list(task.spec.twist_rules),
            difficulty_label=task.difficulty.label,
            critic_score=task.difficulty.critic_score,
            calibration_pass_rate=task.difficulty.calibration_pass_rate,
            story=task.story,
            question=task.question,
            order_sensitive=flag,
            gold_schema_ddl=task.gold.schema_ddl,
            gold_data_inserts=task.gold.data_inserts,
            gold_query=task.gold.query,
            gold_rows=[list(row) for row in task.gold.result.rows],
            gold_columns=list(task.gold.result.columns),
        )

    @staticmethod
    def _require(value: str, field_name: str) -> None:
        """Verifica che un campo obbligatorio non sia vuoto."""
        if not value or not value.strip():
            raise BenchmarkFormatError(f"Campo obbligatorio mancante o vuoto: '{field_name}'.")
