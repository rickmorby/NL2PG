"""Adattatore outbound per la serializzazione ed I/O su filesystem dei task in formato JSON.

:author: Riccardo Morabito
"""

from datetime import datetime, timezone
from pathlib import Path

from orjson import OPT_INDENT_2, dumps as orjson_dumps

from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.serializer_port import BenchmarkSerializerPort
from bench.domain.services.weighted_mean import weighted_mean


class JsonBenchmarkSerializerAdapter(BenchmarkSerializerPort):
    """Adattatore outbound per la serializzazione atomica su filesystem via orjson."""

    def build_document(
        self, tasks: list[TaskStateDTO], run_id: str, weights: dict | None = None,
    ) -> dict:
        """Costruisce il documento JSON della run con tutti i task accettati."""
        accepted = [
            t for t in tasks
            if t.verdict in ("accepted", "accept") and t.story and t.question and t.gold_result
        ]
        return {
            "version": 1,
            "language": "it",
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tasks": [self._build_entry(t, weights or {}) for t in accepted],
        }

    def write(self, document: dict, output_path: Path) -> None:
        """Scrive atomicamente il documento JSON su file temporaneo e lo rimpiazza."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(".tmp")
        tmp_path.write_bytes(orjson_dumps(document, option=OPT_INDENT_2))
        tmp_path.replace(output_path)

    def write_single_task(self, task_dict: dict, output_path: Path) -> None:
        """Scrive atomicamente un singolo task JSON nella cartella di destinazione."""
        self.write(task_dict, output_path)

    def _build_entry(self, state: TaskStateDTO, weights: dict) -> dict:
        """Converte un TaskStateDTO in un dict per l'output JSON."""
        critic_score = weighted_mean(state.critic, weights) if state.critic else None
        rows = list(state.gold_result.rows) if state.gold_result else []
        return {
            "task_id": state.task_id,
            "category": state.category,
            "difficulty": {
                "label": state.difficulty_label,
                "critic_score": critic_score,
                "calibration_pass_rate": state.calibration.pass_rate if state.calibration else None,
                "calibration_model": state.calibration.model if state.calibration else "",
            },
            "spec": state.spec.model_dump() if state.spec else None,
            "story": state.story.story if state.story else "",
            "question": state.question.question if state.question else "",
            "gold": {
                "schema_ddl": state.schema_ddl.ddl if state.schema_ddl else "",
                "data_inserts": state.data_inserts.inserts if state.data_inserts else "",
                "query": state.gold_query.query if state.gold_query else "",
                "result": {
                    "columns": state.gold_result.columns if state.gold_result else [],
                    "rows": rows,
                    "order_sensitive": state.gold_result.order_sensitive
                    if state.gold_result else False,
                },
            },
        }
