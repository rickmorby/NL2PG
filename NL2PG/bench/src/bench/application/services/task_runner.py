"""Servizio applicativo per l'esecuzione batch dei task con output JSON e generazione analytics.

:author: Riccardo Morabito
"""

from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from threading import Lock
from time import time

from bench.application.services.generation_loop import GenerationLoop, _RunContext
from bench.application.services.resume_validator import ResumeValidator
from bench.domain.exceptions import BenchException
from bench.domain.models import BatchSummaryDTO, TaskStateDTO
from bench.domain.ports.inbound.task_runner_port import TaskRunnerPort
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.repository_port import MetaRepositoryPort
from bench.domain.ports.outbound.serializer_port import BenchmarkSerializerPort
from bench.domain.services.category_round_picker import CategoryRoundPicker
from bench.domain.services.domain_pool import DOMAIN_POOL

_log = getLogger("bench.application.task_runner")


class TaskRunner(TaskRunnerPort):
    """Servizio applicativo che coordina la generazione batch ed il salvataggio JSON."""

    def __init__(
        self,
        orchestrator: object,
        meta_repo: MetaRepositoryPort,
        serializer: BenchmarkSerializerPort,
        config: ConfigPort,
        *,
        analytics: object | None = None,
        base_output_dir: Path | None = None,
    ) -> None:
        """Inietta l'orchestratore, il repository, il serializzatore ed analytics."""
        self._orchestrator = orchestrator
        self._meta_repo = meta_repo
        self._serializer = serializer
        self._config = config
        self._analytics = analytics
        self._lock = Lock()
        self._attempt_counter = 0
        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        self._base_output_dir = base_output_dir or (base_dir / "output")
        self._resume_validator = ResumeValidator(serializer, meta_repo)

    def run_batch(
        self,
        count: int | None = None,
        category: str = "",
        batch_size: int = 1,
        resume_path: Path | None = None,
    ) -> BatchSummaryDTO:
        """Esegue una nuova run oppure riprende una run esistente da un JSON."""
        start_time = time()
        categories = self._config.load_categories()
        count, category = self._validate_run_args(count, category, categories, resume_path)

        cfg_hash = self._config.bench_hash()
        cat_hash = self._config.config_hash({"categories": list(categories.keys())})
        run_id, run_file, resume_document, accepted_counts = self._init_or_resume(
            resume_path, cfg_hash, cat_hash, categories
        )
        accepted_count = sum(accepted_counts.values())
        if resume_path is not None and count < accepted_count:
            raise ValueError(
                f"Il limite di resume ({count}) è inferiore ai task già accettati "
                f"({accepted_count})."
            )

        remaining = count - accepted_count
        picker = None if category else CategoryRoundPicker(list(categories.keys()), accepted_counts)
        _log.info(
            "%s run: run_id=%s, target=%d, accepted=%d, remaining=%d, run_file=%s",
            "Resume" if resume_path else "Nuova",
            run_id,
            count,
            accepted_count,
            remaining,
            run_file.name,
        )

        if remaining:
            context = _RunContext(
                run_id=run_id,
                output_file=run_file,
                target_new=remaining,
                requested_count=count,
                category=category,
                batch_size=batch_size,
                document=resume_document,
            )
            loop = GenerationLoop(
                self._orchestrator,
                self._meta_repo,
                self._serializer,
                self._config,
                self._lock,
                self._create_initial_state,
            )
            accepted_tasks = loop.run(context, picker)
            summary = self._build_summary_from_db(
                context.run_id, context.output_file, context.requested_count, accepted_tasks
            )
        else:
            self._serializer.write(resume_document, run_file)
            summary = self._build_summary_from_db(run_id, run_file, count, [])

        duration = round(time() - start_time, 2)
        summary.duration_seconds = duration
        self._try_analytics(run_id, run_file)
        return summary

    @staticmethod
    def _validate_run_args(
        count: int | None,
        category: str,
        categories: dict,
        resume_path: Path | None,
    ) -> tuple[int, str]:
        """Valida e normalizza gli argomenti di ingresso."""
        if count is None:
            count = len(categories)
        if count <= 0:
            raise ValueError("Il limite deve essere maggiore di zero.")
        if category and category not in categories:
            allowed = sorted(list(categories.keys()))
            msg = f"Categoria '{category}' non valida. Categorie disponibili: {allowed}"
            raise ValueError(msg)
        if category and resume_path is not None:
            raise ValueError("--category non può essere usato insieme a --resume.")
        return count, category

    def _init_or_resume(
        self,
        resume_path: Path | None,
        cfg_hash: str,
        cat_hash: str,
        categories: dict,
    ) -> tuple[str, Path, dict, dict[str, int]]:
        """Inizializza una nuova run o prepara il resume da file esistente."""
        if resume_path is None:
            run_id = self._meta_repo.new_run(cfg_hash, cat_hash)
            run_file = self._new_run_file(run_id)
            return run_id, run_file, self._serializer.build_document([], run_id), {}
        return self._resume_validator.validate(resume_path, cfg_hash, cat_hash, categories)

    def _try_analytics(self, run_id: str, run_file: Path) -> None:
        """Tenta la generazione analytics senza propagare errori."""
        if self._analytics:
            try:
                self._analytics.generate_analytics(run_file)
            except (BenchException, OSError, ValueError, RuntimeError) as e:
                _log.warning("Generazione analytics per la run '%s' fallita: %s", run_id, e)

    def _new_run_file(self, run_id: str) -> Path:
        """Crea il percorso del JSON per una nuova run."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        benchmarks_dir = self._base_output_dir / "benchmarks"
        benchmarks_dir.mkdir(parents=True, exist_ok=True)
        return benchmarks_dir / f"run_{timestamp}_{run_id}.json"

    def _create_initial_state(
        self,
        category: str,
        picker: CategoryRoundPicker | None,
    ) -> TaskStateDTO | None:
        """Crea uno stato iniziale assegnando la categoria (a giri) ed il dominio in Round-Robin."""
        with self._lock:
            cat_id = category if category else (picker.pick() if picker is not None else None)
            if cat_id is None:
                return None
            target_domain = DOMAIN_POOL[self._attempt_counter % len(DOMAIN_POOL)]
            self._attempt_counter += 1
        return TaskStateDTO(category=cat_id, target_domain=target_domain)

    def _build_summary_from_db(
        self,
        run_id: str,
        output_file: Path,
        requested_count: int,
        accepted_tasks: list[TaskStateDTO],
    ) -> BatchSummaryDTO:
        """Costruisce il riepilogo BatchSummaryDTO interrogando il DB come fonte unica di verità."""
        db_counts = self._meta_repo.get_run_verdict_counts(run_id)
        covered = {task.category for task in accepted_tasks}
        all_categories = set(self._config.load_categories().keys())
        return BatchSummaryDTO(
            run_id=run_id,
            output_dir=str(output_file.parent),
            requested_count=requested_count,
            accepted_count=db_counts.get("accepted", len(accepted_tasks)),
            rejected_count=db_counts.get("rejected", 0),
            scrapped_count=db_counts.get("scrapped", 0),
            failed_count=db_counts.get("failed", 0),
            categories_covered=len(covered),
            categories_total=len(all_categories),
            missing_categories=sorted(all_categories - covered),
            duration_seconds=0.0,
        )
