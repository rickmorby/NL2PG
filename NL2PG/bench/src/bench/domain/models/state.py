"""Modulo DTO per lo stato della pipeline del benchmark.

:author: Riccardo Morabito
"""

from pydantic import field_validator

from bench.domain.exceptions.domain_exc import DomainValidationError
from bench.domain.models.base import AbstractDTO
from bench.domain.models.nlp import CalibrationResultDTO, CriticScoresDTO, QuestionDTO, StoryDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.models.sql import DataInsertsDTO, GoldQueryDTO, GoldResultDTO, SchemaDDLDTO

_ALLOWED_VERDICTS = frozenset({"pending", "accepted", "accept", "rejected", "scrapped", "failed"})


class TaskStateDTO(AbstractDTO):
    """Stato dell'esecuzione del task attraverso la pipeline con invarianti di dominio."""

    task_id: str = ""
    run_id: str = ""
    category: str = ""
    target_domain: str = ""
    sandbox_schema: str = ""
    spec: SpecDTO | None = None
    schema_ddl: SchemaDDLDTO | None = None
    data_inserts: DataInsertsDTO | None = None
    gold_query: GoldQueryDTO | None = None
    gold_result: GoldResultDTO | None = None
    story: StoryDTO | None = None
    question: QuestionDTO | None = None
    critic: CriticScoresDTO | None = None
    calibration: CalibrationResultDTO | None = None
    verdict: str = "pending"
    retry_schema: int = 0
    retry_data: int = 0
    retry_query: int = 0
    retry_story: int = 0
    retry_question: int = 0
    retry_critic: int = 0
    retry_hardening: int = 0
    judge_regens: int = 0
    judge_verdict: str = ""
    difficulty_label: str = ""
    last_model: str = ""
    last_error: str = ""

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        """Verifica che il verdetto appartenga agli stati ammessi nel dominio."""
        if v and v not in _ALLOWED_VERDICTS:
            msg = f"Verdetto '{v}' non valido per il task. Ammessi: {sorted(_ALLOWED_VERDICTS)}"
            raise DomainValidationError(msg, payload={"verdict": v})
        return v
