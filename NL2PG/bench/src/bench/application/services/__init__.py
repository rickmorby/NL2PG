"""Modulo dei servizi applicativi per l'esecuzione in batch dei task del benchmark.

:author: Riccardo Morabito
"""

from bench.application.services.task_runner import BatchSummaryDTO, TaskRunner

__all__: list[str] = [
    "BatchSummaryDTO",
    "TaskRunner",
]
