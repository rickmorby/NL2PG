"""Servizio applicativo per l'esecuzione batch dei task con output JSON e generazione analytics.

:author: Riccardo Morabito
"""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from threading import Lock
from time import time

from tqdm import tqdm

from bench.application.orchestrator.orchestrator import Orchestrator
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
        count: int = 10,
        category: str = "",
        batch_size: int = 1,
    ) -> BatchSummaryDTO:
        """Esegue una run di generazione in modalità sequenziale o parallela."""
        start_time = time()
        categories = self._config.load_categories()
        if category and category not in categories:
            allowed = sorted(list(categories.keys()))
            msg = f"Categoria '{category}' non valida. Categorie disponibili: {allowed}"
            raise ValueError(msg)
        picker = None if category else CategoryRoundPicker(list(categories.keys()))

        cfg_hash = self._config.bench_hash()
        cat_hash = self._config.config_hash({"categories": list(categories.keys())})

        run_id = self._meta_repo.new_run(cfg_hash, cat_hash)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        benchmarks_dir = self._base_output_dir / "benchmarks"
        benchmarks_dir.mkdir(parents=True, exist_ok=True)
        run_file = benchmarks_dir / f"run_{timestamp}_{run_id}.json"

        _log.info("Nuova run avviata: run_id=%s, run_file=%s", run_id, run_file.name)

        if batch_size > 1:
            summary = self._run_parallel(
                run_info=(run_id, run_file, count, category, batch_size),
                picker=picker,
            )
        else:
            summary = self._run_sequential(
                run_id=run_id,
                output_file=run_file,
                count=count,
                category=category,
                picker=picker,
            )

        duration = round(time() - start_time, 2)
        summary.duration_seconds = duration

        if self._analytics:
            try:
                self._analytics.generate_analytics(run_file)
            except Exception as e:
                _log.warning("Generazione analytics per la run '%s' fallita: %s", run_id, e)

        return summary

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
        accepted_tasks: list[TaskStateDTO],
        counts: dict[str, int],
        run_file: Path,
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
                doc = self._serializer.build_document(accepted_tasks, result_state.run_id, weights)
                self._serializer.write(doc, run_file)
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

    def _run_sequential(
        self,
        run_id: str,
        output_file: Path,
        count: int,
        category: str,
        picker: CategoryRoundPicker | None,
    ) -> BatchSummaryDTO:
        """Esegue la generazione sequenziale di task uno alla volta."""
        max_fails = self._config.cli_max_consecutive_failures()
        failure_warning_threshold = self._config.cli_category_failure_warning()
        accepted_tasks: list[TaskStateDTO] = []
        counts = {"rejected": 0, "scrapped": 0, "failed": 0}
        consecutive_failures = 0

        with tqdm(total=count, desc="Generazione Task (Sequenziale)", smoothing=0.1) as pbar:
            while len(accepted_tasks) < count:
                initial_state = self._create_initial_state(category, picker)
                if initial_state is None:
                    break
                result_state = self._orchestrator.run_task(initial_state, run_id)
                self._meta_repo.save_task(run_id, result_state)

                fail_delta = self._process_verdict(
                    result_state,
                    accepted_tasks,
                    counts,
                    output_file,
                    picker,
                    failure_warning_threshold,
                )
                if result_state.verdict in ("accepted", "accept"):
                    pbar.update(1)
                if fail_delta > 0:
                    consecutive_failures += fail_delta
                    if consecutive_failures >= max_fails:
                        _log.warning("Circuit breaker: %d fallimenti.", consecutive_failures)
                        break
                else:
                    consecutive_failures = 0

                pbar.set_postfix(
                    acc=len(accepted_tasks),
                    rej=counts["rejected"],
                    verdict=result_state.verdict,
                )

        return self._build_summary_from_db(run_id, output_file, count, accepted_tasks)

    def _run_parallel(
        self,
        run_info: tuple[str, Path, int, str, int],
        picker: CategoryRoundPicker | None,
    ) -> BatchSummaryDTO:
        """Esegue la generazione parallela in batch tramite ThreadPoolExecutor con Lock."""
        run_id, output_file, count, _category, batch_size = run_info
        max_fails = self._config.cli_max_consecutive_failures()
        failure_warning_threshold = self._config.cli_category_failure_warning()
        accepted_tasks: list[TaskStateDTO] = []
        counts = {"rejected": 0, "scrapped": 0, "failed": 0}
        consecutive_failures = 0

        desc = f"Generazione Task (Parallel {batch_size})"
        with (
            tqdm(total=count, desc=desc, smoothing=0.1) as pbar,
            ThreadPoolExecutor(max_workers=batch_size) as executor,
        ):
            futures: dict = {}
            self._submit_pending(executor, futures, accepted_tasks, run_info, picker)

            while futures and consecutive_failures < max_fails:
                done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    cat_id = futures.pop(fut)
                    try:
                        result_state = fut.result()
                        self._meta_repo.save_task(run_id, result_state)
                        fail_delta = self._process_verdict(
                            result_state,
                            accepted_tasks,
                            counts,
                            output_file,
                            picker,
                            failure_warning_threshold,
                        )
                        if result_state.verdict in ("accepted", "accept"):
                            pbar.update(1)
                        if fail_delta > 0:
                            consecutive_failures += fail_delta
                        else:
                            consecutive_failures = 0
                    except Exception as e:
                        _log.debug("Errore task parallelo per categoria '%s': %s", cat_id, e)
                        counts["failed"] += 1
                        consecutive_failures += 1
                        self._resolve_category(cat_id, False, picker, failure_warning_threshold)

                    self._submit_pending(executor, futures, accepted_tasks, run_info, picker)

                    pbar.set_postfix(
                        acc=len(accepted_tasks),
                        active=len(futures),
                        cat=cat_id,
                    )

            if consecutive_failures >= max_fails:
                _log.warning("Circuit breaker: %d fallimenti.", consecutive_failures)
                for pending in futures:
                    pending.cancel()

        return self._build_summary_from_db(run_id, output_file, count, accepted_tasks)

    def _submit_pending(
        self,
        executor: ThreadPoolExecutor,
        futures: dict,
        accepted_tasks: list[TaskStateDTO],
        run_info: tuple[str, Path, int, str, int],
        picker: CategoryRoundPicker | None,
    ) -> None:
        """Sottomette nuovi task finché il batch è pieno e la richiesta non è soddisfatta."""
        run_id, _output_file, count, category, batch_size = run_info
        while len(futures) < batch_size and (len(accepted_tasks) + len(futures)) < count:
            init_state = self._create_initial_state(category, picker)
            if init_state is None:
                break
            fut = executor.submit(self._orchestrator.run_task, init_state, run_id)
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
