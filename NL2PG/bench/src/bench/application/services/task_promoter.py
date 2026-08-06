"""Servizio applicativo per la promozione dei task accettati nelle directory di esempio.

:author: Riccardo Morabito
"""

from json import loads
from logging import getLogger
from pathlib import Path

from bench.application.serializer.serializer import BenchmarkSerializer

_log = getLogger("bench.application.task_promoter")


class TaskPromoterService:
    """Servizio applicativo che coordina la promozione dei task accettati."""

    def __init__(self, serializer: BenchmarkSerializer) -> None:
        """Inietta l'aggregato unico di serializzazione."""
        self._serializer = serializer

    def promote_accepted_tasks(self, output_dir: Path, examples_dir: Path) -> int:
        """Legge i file JSON di run da output_dir e li promuove in examples/<cat>/."""
        if not output_dir.exists():
            _log.info("Directory output '%s' non esistente.", output_dir)
            return 0

        json_files = sorted(
            list(output_dir.glob("run_*.json"))
            + list(output_dir.rglob("benchmark_samples.json"))
        )

        promoted_count = 0
        for sample_file in json_files:
            try:
                doc = loads(sample_file.read_text(encoding="utf-8"))
                for task in doc.get("tasks", []):
                    cat = task.get("category", "unknown")
                    cat_dir = examples_dir / cat
                    task_file = cat_dir / f"{task['task_id']}.json"
                    self._serializer.write_single_task(task, task_file)
                    promoted_count += 1
            except Exception as e:
                _log.warning("Errore durante la promozione del file '%s': %s", sample_file.name, e)

        return promoted_count
