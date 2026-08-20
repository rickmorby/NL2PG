"""Servizio applicativo per l'esecuzione batch dei task con output JSON e generazione analytics.

:author: Riccardo Morabito
"""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from threading import Lock
from time import time

from psycopg.errors import Error as PgError
from pydantic import ValidationError
from sqlglot.errors import ParseError
from tqdm import tqdm

from bench.application.orchestrator.orchestrator import Orchestrator
from bench.domain.exceptions import BenchException
from bench.domain.models import BatchSummaryDTO, TaskStateDTO
from bench.domain.ports.inbound.task_runner_port import TaskRunnerPort
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.repository_port import MetaRepositoryPort
from bench.domain.ports.outbound.serializer_port import BenchmarkSerializerPort
from bench.domain.services.category_round_picker import CategoryRoundPicker
from bench.domain.services.domain_pool import DOMAIN_POOL

_log = getLogger("bench.application.task_runner")


@dataclass(frozen=True)
class _RunContext:
    """Contesto immutabile di una singola esecuzione del loop di generazione."""

    run_id: str
    output_file: Path
    target_new: int
    requested_count: int
    category: str
    batch_size: int
    document: dict


class TaskRunner(TaskRunnerPort):
    """Servizio applicativo che coordina la generazione batch ed il salvataggio JSON."""

    def __init__(
        self,
        orchestrator: Orchestrator,
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
            summary = self._run_generation(context, picker)
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
        return self._prepare_resume(resume_path, cfg_hash, cat_hash, categories)

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

    def _prepare_resume(
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

    def _process_verdict(
        self,
        result_state: TaskStateDTO,
        context: _RunContext,
        accepted_tasks: list[TaskStateDTO],
        counts: dict[str, int],
        picker: CategoryRoundPicker | None,
        failure_warning_threshold: int,
    ) -> int:
        """Elabora l'esito di un task aggiornando livelli, contatori e file di output."""
        verdict = result_state.verdict
        accepted = verdict in ("accepted", "accept")
        self._resolve_category(result_state.category, accepted, picker, failure_warning_threshold)
        if accepted:
            with self._lock:
                accepted_tasks.append(result_state)
                weights = self._config.critic_weights()
                doc = self._serializer.merge_tasks(context.document, [result_state], weights)
                self._serializer.write(doc, context.output_file)
            return 0
        if verdict == "rejected":
            counts["rejected"] += 1
            return 0
        if verdict == "scrapped":
            counts["scrapped"] += 1
            return 0
        counts["failed"] += 1
        return 1

    def _resolve_category(
        self,
        category: str,
        accepted: bool,
        picker: CategoryRoundPicker | None,
        failure_warning_threshold: int,
    ) -> None:
        """Aggiorna il livello della categoria ed avvisa dopo troppi fallimenti consecutivi."""
        with self._lock:
            failures = picker.resolve(category, accepted) if picker is not None else 0
        if failures == failure_warning_threshold:
            _log.warning("Categoria '%s': %d tentativi falliti consecutivi.", category, failures)

    def _run_generation(
        self,
        context: _RunContext,
        picker: CategoryRoundPicker | None,
    ) -> BatchSummaryDTO:
        """Esegue la generazione dei task con un pool di worker (1 worker = sequenziale)."""
        max_fails = self._config.cli_max_consecutive_failures()
        failure_warning_threshold = self._config.cli_category_failure_warning()
        accepted_tasks: list[TaskStateDTO] = []
        counts = {"rejected": 0, "scrapped": 0, "failed": 0}
        consecutive_failures = 0
        desc = (
            "Generazione Task (Sequenziale)"
            if context.batch_size == 1
            else f"Generazione Task (Parallel {context.batch_size})"
        )
        with tqdm(total=context.target_new, desc=desc, smoothing=0.1) as pbar:
            executor = ThreadPoolExecutor(max_workers=context.batch_size)
            try:
                futures: dict = {}
                self._submit_pending(executor, futures, accepted_tasks, context, picker)
                while futures and consecutive_failures < max_fails:
                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                    for fut in done:
                        cat_id = futures.pop(fut)
                        try:
                            result_state = fut.result()
                            self._meta_repo.save_task(context.run_id, result_state)
                            fail_delta = self._process_verdict(
                                result_state,
                                context,
                                accepted_tasks,
                                counts,
                                picker,
                                failure_warning_threshold,
                            )
                            if result_state.verdict in ("accepted", "accept"):
                                pbar.update(1)
                            if fail_delta > 0:
                                consecutive_failures += fail_delta
                            else:
                                consecutive_failures = 0
                        except (
                            BenchException,
                            PgError,
                            ParseError,
                            ValidationError,
                            ValueError,
                            RuntimeError,
                        ) as e:
                            _log.debug("Errore task per categoria '%s': %s", cat_id, e)
                            counts["failed"] += 1
                            consecutive_failures += 1
                            self._resolve_category(cat_id, False, picker, failure_warning_threshold)
                        self._submit_pending(executor, futures, accepted_tasks, context, picker)
                        pbar.set_postfix(
                            acc=len(accepted_tasks),
                            active=len(futures),
                            cat=cat_id,
                        )
                if consecutive_failures >= max_fails:
                    _log.warning("Circuit breaker: %d fallimenti.", consecutive_failures)
                    for pending in futures:
                        pending.cancel()
            except KeyboardInterrupt:
                executor.shutdown(wait=False, cancel_futures=True)
                _log.warning("Interruzione da tastiera: task in coda annullati.")
                raise
            else:
                executor.shutdown(wait=True)

        return self._build_summary_from_db(
            context.run_id, context.output_file, context.requested_count, accepted_tasks
        )

    def _submit_pending(
        self,
        executor: ThreadPoolExecutor,
        futures: dict,
        accepted_tasks: list[TaskStateDTO],
        context: _RunContext,
        picker: CategoryRoundPicker | None,
    ) -> None:
        """Sottomette nuovi task finché il batch è pieno e la richiesta non è soddisfatta."""
        while (
            len(futures) < context.batch_size
            and (len(accepted_tasks) + len(futures)) < context.target_new
        ):
            init_state = self._create_initial_state(context.category, picker)
            if init_state is None:
                break
            fut = executor.submit(self._orchestrator.run_task, init_state, context.run_id)
            futures[fut] = init_state.category

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
