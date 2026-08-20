"""Modulo DTO per i documenti ed i riepiloghi del benchmark.

:author: Riccardo Morabito
"""

from pydantic import Field

from bench.domain.models.base import AbstractDTO


class RunMetadataDTO(AbstractDTO):
    """Metadati persistiti necessari per validare il resume di una run."""

    run_id: str = ""
    config_hash: str = ""
    categories_hash: str = ""


class BatchSummaryDTO(AbstractDTO):
    """DTO per il riepilogo finale dell'esecuzione batch di una run."""

    run_id: str = ""
    output_dir: str = ""
    requested_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    scrapped_count: int = 0
    failed_count: int = 0
    categories_covered: int = 0
    categories_total: int = 0
    missing_categories: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
