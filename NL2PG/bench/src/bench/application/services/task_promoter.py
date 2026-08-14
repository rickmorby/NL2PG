"""Servizio applicativo per la promozione dei task accettati nelle directory di esempio.

:author: Riccardo Morabito
"""

from logging import getLogger
from pathlib import Path

from bench.domain.ports.inbound.task_promoter_port import TaskPromoterPort
from bench.domain.ports.outbound.serializer_port import BenchmarkSerializerPort
from bench.domain.services.role_example_builder import RoleExampleBuilder

_log = getLogger("bench.application.task_promoter")


class TaskPromoterService(TaskPromoterPort):
    """Servizio applicativo che coordina la promozione dei task accettati."""

    def __init__(self, serializer: BenchmarkSerializerPort, builder: RoleExampleBuilder) -> None:
        """Inietta l'aggregato unico di serializzazione e il builder delle proiezioni ruolo."""
        self._serializer = serializer
        self._builder = builder

    def promote_accepted_tasks(self, output_dir: Path, examples_dir: Path) -> int:
        """Legge i file di run e promuove esempi role-specific in examples/<cat>/<ruolo>/."""
        if not output_dir.exists():
            _log.info("Directory output '%s' non esistente.", output_dir)
            return 0

        json_files = sorted(
            list(output_dir.glob("run_*.json"))
            + list(output_dir.glob("benchmarks/run_*.json"))
            + list(output_dir.rglob("benchmark_samples.json"))
        )

        promoted_count = 0
        for sample_file in json_files:
            try:
                doc = self._serializer.read(sample_file)
                for task in doc.get("tasks", []):
                    cat = task.get("category", "unknown")
                    task_id = task.get("task_id", "unknown")
                    for role in self._builder.roles():
                        example = self._builder.build(task, role)
                        role_dir = examples_dir / cat / role
                        self._serializer.write_single_task(example, role_dir / f"{task_id}.json")
                        promoted_count += 1
            except Exception as e:
                _log.warning("Errore durante la promozione del file '%s': %s", sample_file.name, e)

        return promoted_count
