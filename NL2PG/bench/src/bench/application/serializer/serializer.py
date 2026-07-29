"""Servizio per serializzare i risultati del benchmark in formato JSON.

:author: Riccardo Morabito
"""

from datetime import datetime, timezone
from json import dumps
from pathlib import Path

from bench.domain.models.state import TaskStateDTO
from bench.domain.services.weighted_mean import weighted_mean


class BenchmarkSerializer:
    """Serializza i task completati in un singolo file JSON per run."""

    def build_document(
        self, tasks: list[TaskStateDTO], run_id: str, weights: dict | None = None,
    ) -> dict:
        """Costruisce il documento JSON della run con tutti i task accettati."""
        accepted = [
            t for t in tasks
            if t.verdict == "accept" and t.story and t.question and t.gold_result
        ]
        return {
            "version": 1,
            "language": "it",
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tasks": [self._build_entry(t, weights or {}) for t in accepted],
        }

    def write(self, document: dict, output_path: Path) -> None:
        """Scrive il documento JSON su file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            dumps(document, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

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
