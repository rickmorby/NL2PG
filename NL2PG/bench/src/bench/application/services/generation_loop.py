"""Motore di generazione batch con pool di worker e gestione SIGINT.

:author: Riccardo Morabito
"""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from threading import Lock
from typing import Callable

from psycopg.errors import Error as PgError
from pydantic import ValidationError
from sqlglot.errors import ParseError
from tqdm import tqdm

from bench.domain.exceptions import BenchException
from bench.domain.models import TaskStateDTO
from bench.domain.services.picking.category_round_picker import CategoryRoundPicker

_log = getLogger("bench.application.generation_loop")


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


class GenerationLoop:
    """Esegue la generazione dei task con un pool di worker (1 worker = sequenziale)."""

    def __init__(
        self,
        orchestrator: object,
        meta_repo: object,
        serializer: object,
        config: object,
        lock: Lock,
        create_state: Callable[[str, CategoryRoundPicker | None], TaskStateDTO | None],
    ) -> None:
        """Inietta le dipendenze condivise e la factory di stato iniziale."""
        self._orchestrator = orchestrator
        self._meta_repo = meta_repo
        self._serializer = serializer
        self._config = config
        self._lock = lock
        self._create_state = create_state

    def run(
        self,
        context: _RunContext,
        picker: CategoryRoundPicker | None,
    ) -> list[TaskStateDTO]:
        """Esegue il loop di generazione e restituisce i task accepted prodotti."""
        max_fails = self._config.cli_max_consecutive_failures()  # type: ignore[attr-defined]
        failure_warning_threshold = self._config.cli_category_failure_warning()  # type: ignore[attr-defined]
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
                            self._meta_repo.save_task(context.run_id, result_state)  # type: ignore[attr-defined]
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
        return accepted_tasks

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
                weights = self._config.critic_weights()  # type: ignore[attr-defined]
                doc = self._serializer.merge_tasks(context.document, [result_state], weights)  # type: ignore[attr-defined]
                self._serializer.write(doc, context.output_file)  # type: ignore[attr-defined]
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
            init_state = self._create_state(context.category, picker)
            if init_state is None:
                break
            fut = executor.submit(self._orchestrator.run_task, init_state, context.run_id)  # type: ignore[attr-defined]
            futures[fut] = init_state.category
