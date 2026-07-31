"""Modulo DTO per i documenti ed i riepiloghi del benchmark.

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import Field
from bench.domain.models.base import AbstractDTO


class DifficultyDocumentDTO(AbstractDTO):
    """Difficoltà del task per l'esportazione."""

    label: str = ""
    critic_score: float | None = None
    calibration_pass_rate: float | None = None
    calibration_model: str = ""


class GoldResultDocumentDTO(AbstractDTO):
    """Risultato Gold per l'esportazione."""

    columns: list[str] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    order_sensitive: bool = False


class GoldDocumentDTO(AbstractDTO):
    """Insieme di schema, dati, query e risultato Gold."""

    schema_ddl: str = ""
    data_inserts: str = ""
    query: str = ""
    result: GoldResultDocumentDTO | None = None


class EvaluationDocumentDTO(AbstractDTO):
    """Parametri per la valutazione del benchmark."""

    schema_matching: str = "normalized_names"
    result_comparison: str = "bag_semantics"


class BenchmarkTaskDocumentDTO(AbstractDTO):
    """Documento completo del task per l'esportazione."""

    id: str = ""
    version: int = 1
    language: str = "it"
    category: str = ""
    spec: dict[str, Any] | None = None
    difficulty: DifficultyDocumentDTO = Field(default_factory=DifficultyDocumentDTO)
    story: str = ""
    question: str = ""
    gold: GoldDocumentDTO = Field(default_factory=GoldDocumentDTO)
    evaluation: EvaluationDocumentDTO = Field(default_factory=EvaluationDocumentDTO)


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
