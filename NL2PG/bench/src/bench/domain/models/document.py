"""Modulo DTO per i documenti ed i riepiloghi del benchmark.

:author: Riccardo Morabito
"""

from bench.domain.models.base import AbstractDTO


class BatchSummaryDTO(AbstractDTO):
    """DTO per il riepilogo finale dell'esecuzione batch di una run."""

    run_id: str = ""
    output_dir: str = ""
    requested_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    scrapped_count: int = 0
    failed_count: int = 0
    duration_seconds: float = 0.0
