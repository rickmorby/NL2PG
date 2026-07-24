"""Modulo DTO per lo stato della pipeline del benchmark.

:author: Riccardo Morabito
"""

from pydantic import PrivateAttr
from bench.models.base import AbstractDTO
from bench.models.spec import SpecDTO
from bench.models.sql import SchemaDDLDTO, DataInsertsDTO, GoldQueryDTO, GoldResultDTO
from bench.models.nlp import StoryDTO, QuestionDTO, CriticScoresDTO, CalibrationResultDTO


class TaskStateDTO(AbstractDTO):
    """Stato dell'esecuzione del task attraverso la pipeline."""

    _task_id: str = PrivateAttr(default="")
    _run_id: str = PrivateAttr(default="")
    _category: str = PrivateAttr(default="")
    _sandbox_schema: str = PrivateAttr(default="")
    _spec: SpecDTO | None = PrivateAttr(default=None)
    _schema_ddl: SchemaDDLDTO | None = PrivateAttr(default=None)
    _data_inserts: DataInsertsDTO | None = PrivateAttr(default=None)
    _gold_query: GoldQueryDTO | None = PrivateAttr(default=None)
    _gold_result: GoldResultDTO | None = PrivateAttr(default=None)
    _story: StoryDTO | None = PrivateAttr(default=None)
    _question: QuestionDTO | None = PrivateAttr(default=None)
    _critic: CriticScoresDTO | None = PrivateAttr(default=None)
    _calibration: CalibrationResultDTO | None = PrivateAttr(default=None)
    _verdict: str = PrivateAttr(default="pending")
    _retry_schema: int = PrivateAttr(default=0)
    _retry_data: int = PrivateAttr(default=0)
    _retry_query: int = PrivateAttr(default=0)
    _retry_story: int = PrivateAttr(default=0)
    _retry_question: int = PrivateAttr(default=0)
    _retry_critic: int = PrivateAttr(default=0)
    _retry_hardening: int = PrivateAttr(default=0)
    _judge_regens: int = PrivateAttr(default=0)
    _judge_verdict: str = PrivateAttr(default="")
    _difficulty_label: str = PrivateAttr(default="")
    _last_model: str = PrivateAttr(default="")
    _last_error: str = PrivateAttr(default="")
