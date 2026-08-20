"""Validazione di coerenza per il resume di una run interrotta.

:author: Riccardo Morabito
"""

from pathlib import Path

from bench.domain.ports.outbound.repository_port import MetaRepositoryPort
from bench.domain.ports.outbound.serializer_port import BenchmarkSerializerPort


class ResumeValidator:
    """Verifica la coerenza tra JSON esistente e metadati persistiti."""

    def __init__(
        self,
        serializer: BenchmarkSerializerPort,
        meta_repo: MetaRepositoryPort,
    ) -> None:
        """Inietta le porte di serializzazione e persistenza."""
        self._serializer = serializer
        self._meta_repo = meta_repo

    def validate(
        self,
        resume_path: Path,
        config_hash: str,
        categories_hash: str,
        categories: dict,
    ) -> tuple[str, Path, dict, dict[str, int]]:
        """Valida JSON e database e ricostruisce lo stato accepted della run."""
        path = resume_path.expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"File di resume non trovato: {path}")
        document = self._serializer.read(path)
        run_id = document.get("run_id", "")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("Il documento di resume non contiene un run_id valido.")
        metadata = self._meta_repo.get_run_metadata(run_id)
        if metadata is None:
            raise ValueError(f"La run '{run_id}' non esiste nel database dei metadati.")
        if metadata.config_hash != config_hash:
            raise ValueError("La configurazione bench.toml non corrisponde a quella della run.")
        if metadata.categories_hash != categories_hash:
            raise ValueError("Il catalogo categories.json non corrisponde a quello della run.")
        json_counts = self._count_json_tasks(document, categories)
        db_counts = self._meta_repo.get_accepted_counts_by_category(run_id)
        if db_counts != json_counts:
            raise ValueError(
                "JSON e database non sono allineati sui task accepted; "
                "resume annullato per evitare perdita di dati."
            )
        return run_id, path, document, db_counts

    @staticmethod
    def _count_json_tasks(document: dict, categories: dict) -> dict[str, int]:
        """Conta i task accepted per categoria presenti nel JSON."""
        tasks = document.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("Il documento di resume deve contenere una lista 'tasks'.")
        json_counts: dict[str, int] = {}
        task_ids: set[str] = set()
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Il documento di resume contiene un task non valido.")
            task_id = task.get("task_id")
            task_category = task.get("category")
            if not isinstance(task_id, str) or not task_id or task_id in task_ids:
                raise ValueError("Il documento di resume contiene task_id mancanti o duplicati.")
            if task_category not in categories:
                raise ValueError(
                    f"Il documento di resume contiene categoria sconosciuta: {task_category}"
                )
            task_ids.add(task_id)
            json_counts[task_category] = json_counts.get(task_category, 0) + 1
        return json_counts
