"""Servizio applicativo per l'esecuzione batch dei task con output JSON e generazione analytics.

:author: Riccardo Morabito
"""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from random import choice
from threading import Lock
from time import time

from tqdm import tqdm

from bench.application.orchestrator.orchestrator import Orchestrator
from bench.application.serializer.serializer import BenchmarkSerializer
from bench.domain.models import BatchSummaryDTO, TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.repository_port import MetaRepositoryPort
from bench.domain.services.domain_pool import DOMAIN_POOL

_log = getLogger("bench.application.task_runner")


class TaskRunner:
    """Servizio applicativo che coordina la generazione batch ed il salvataggio JSON."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        meta_repo: MetaRepositoryPort,
        serializer: BenchmarkSerializer,
        config: ConfigPort,
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

        bench_cfg = self._config.load_bench()
        cfg_hash = self._config.config_hash(bench_cfg)
        cat_hash = self._config.config_hash({"categories": list(categories.keys())})

        run_id = self._meta_repo.new_run(cfg_hash, cat_hash)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        benchmarks_dir = self._base_output_dir / "benchmarks"
        benchmarks_dir.mkdir(parents=True, exist_ok=True)
        run_file = benchmarks_dir / f"run_{timestamp}_{run_id}.json"

        _log.info("Nuova run avviata: run_id=%s, run_file=%s", run_id, run_file.name)

        if batch_size > 1:
            summary = self._run_parallel(
                run_id=run_id,
                output_file=run_file,
                count=count,
                category=category,
                batch_size=batch_size,
                bench_cfg=bench_cfg,
            )
        else:
            summary = self._run_sequential(
                run_id=run_id,
                output_file=run_file,
                count=count,
                category=category,
                bench_cfg=bench_cfg,
            )

        duration = round(time() - start_time, 2)
        summary.duration_seconds = duration

        if self._analytics and hasattr(self._analytics, "generate_analytics"):
            try:
                self._analytics.generate_analytics(run_file)
            except Exception as e:
                _log.warning("Generazione analytics per la run '%s' fallita: %s", run_id, e)

        return summary

    def _run_sequential(
        self,
        run_id: str,
        output_file: Path,
        count: int,
        category: str,
        bench_cfg: dict,
    ) -> BatchSummaryDTO:
        """Esegue la generazione sequenziale di task uno alla volta."""
        categories = list(self._config.load_categories().keys())
        max_fails = bench_cfg.get("cli", {}).get("max_consecutive_failures", 5)
        accepted_tasks: list[TaskStateDTO] = []
        rejected_count = 0
        scrapped_count = 0
        failed_count = 0
        consecutive_failures = 0

        with tqdm(total=count, desc="Generazione Task (Sequenziale)", smoothing=0.1) as pbar:
            while len(accepted_tasks) < count:
                cat_id = category if category else choice(categories)
                with self._lock:
                    target_domain = DOMAIN_POOL[self._attempt_counter % len(DOMAIN_POOL)]
                    self._attempt_counter += 1
                initial_state = TaskStateDTO(category=cat_id, target_domain=target_domain)

                result_state = self._orchestrator.run_task(initial_state, run_id)
                self._meta_repo.save_task(run_id, result_state)

                if result_state.verdict in ("accepted", "accept"):
                    with self._lock:
                        accepted_tasks.append(result_state)
                        consecutive_failures = 0
                        pbar.update(1)

                        weights = bench_cfg.get("critic", {}).get("weights", {})
                        doc = self._serializer.build_document(accepted_tasks, run_id, weights)
                        self._serializer.write(doc, output_file)
                elif result_state.verdict == "rejected":
                    rejected_count += 1
                    consecutive_failures = 0
                elif result_state.verdict == "scrapped":
                    scrapped_count += 1
                    consecutive_failures = 0
                else:
                    failed_count += 1
                    consecutive_failures += 1
                    if consecutive_failures >= max_fails:
                        _log.warning("Circuit breaker: %d fallimenti.", consecutive_failures)
                        break

                pbar.set_postfix(
                    acc=len(accepted_tasks),
                    rej=rejected_count,
                    verdict=result_state.verdict,
                )

        return BatchSummaryDTO(
            run_id=run_id,
            output_dir=str(output_file.parent),
            requested_count=count,
            accepted_count=len(accepted_tasks),
            rejected_count=rejected_count,
            scrapped_count=scrapped_count,
            failed_count=failed_count,
            duration_seconds=0.0,
        )

    def _run_parallel(
        self,
        run_id: str,
        output_file: Path,
        count: int,
        category: str,
        batch_size: int,
        bench_cfg: dict,
    ) -> BatchSummaryDTO:
        """Esegue la generazione parallela in batch tramite ThreadPoolExecutor con Lock."""
        categories = list(self._config.load_categories().keys())
        max_fails = bench_cfg.get("cli", {}).get("max_consecutive_failures", 5)
        accepted_tasks: list[TaskStateDTO] = []
        rejected_count = 0
        scrapped_count = 0
        failed_count = 0
        consecutive_failures = 0

        desc = f"Generazione Task (Parallel {batch_size})"
        with tqdm(total=count, desc=desc, smoothing=0.1) as pbar:
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = {}

                while len(futures) < batch_size and (len(accepted_tasks) + len(futures)) < count:
                    cat_id = category if category else choice(categories)
                    init_state = TaskStateDTO(category=cat_id)
                    fut = executor.submit(self._orchestrator.run_task, init_state, run_id)
                    futures[fut] = cat_id

                while futures and consecutive_failures < max_fails:
                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                    for fut in done:
                        cat_id = futures.pop(fut)
                        try:
                            result_state = fut.result()
                            self._meta_repo.save_task(run_id, result_state)

                            if result_state.verdict in ("accepted", "accept"):
                                with self._lock:
                                    accepted_tasks.append(result_state)
                                    consecutive_failures = 0
                                    pbar.update(1)

                                    weights = bench_cfg.get("critic", {}).get("weights", {})
                                    doc = self._serializer.build_document(
                                        accepted_tasks, run_id, weights
                                    )
                                    self._serializer.write(doc, output_file)
                            elif result_state.verdict == "rejected":
                                rejected_count += 1
                                consecutive_failures = 0
                            elif result_state.verdict == "scrapped":
                                scrapped_count += 1
                                consecutive_failures = 0
                            else:
                                failed_count += 1
                                consecutive_failures += 1
                        except Exception as e:
                            _log.error("Errore task parallelo per categoria '%s': %s", cat_id, e)
                            failed_count += 1
                            consecutive_failures += 1

                        while len(futures) < batch_size and (
                            len(accepted_tasks) + len(futures)
                        ) < count:
                            next_cat = category if category else choice(categories)
                            with self._lock:
                                target_domain = DOMAIN_POOL[
                                    self._attempt_counter % len(DOMAIN_POOL)
                                ]
                                self._attempt_counter += 1
                            next_state = TaskStateDTO(
                                category=next_cat, target_domain=target_domain
                            )
                            new_fut = executor.submit(
                                self._orchestrator.run_task, next_state, run_id
                            )
                            futures[new_fut] = next_cat

                        pbar.set_postfix(
                            acc=len(accepted_tasks),
                            active=len(futures),
                            cat=cat_id,
                        )

                if consecutive_failures >= max_fails:
                    _log.warning("Circuit breaker: %d fallimenti.", consecutive_failures)
                    for pending in futures:
                        pending.cancel()

        return BatchSummaryDTO(
            run_id=run_id,
            output_dir=str(output_file.parent),
            requested_count=count,
            accepted_count=len(accepted_tasks),
            rejected_count=rejected_count,
            scrapped_count=scrapped_count,
            failed_count=failed_count,
            duration_seconds=0.0,
        )
