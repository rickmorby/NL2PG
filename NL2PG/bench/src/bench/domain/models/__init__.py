"""Modulo package dei modelli DTO per il benchmark sintetico.

:author: Riccardo Morabito
"""

from bench.domain.models.analytics import AnalyticsDTO
from bench.domain.models.base import AbstractDTO
from bench.domain.models.category import CategoryDTO
from bench.domain.models.document import BatchSummaryDTO, RunMetadataDTO
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO, ConfigCheckResultDTO
from bench.domain.models.nlp import (
    CalibrationResultDTO,
    CriticScoresDTO,
    JudgeDTO,
    QuestionDTO,
    StoryDTO,
)
from bench.domain.models.spec import SpecDTO, TwistRuleDTO
from bench.domain.models.sql import (
    DataInsertsDTO,
    GoldQueryDTO,
    GoldResultDTO,
    SchemaDDLDTO,
    SolverOutputDTO,
)
from bench.domain.models.state import TaskStateDTO

__all__ = [
    "AbstractDTO",
    "AnalyticsDTO",
    "BatchSummaryDTO",
    "CalibrationResultDTO",
    "CallOptionsDTO",
    "CallResultDTO",
    "CategoryDTO",
    "ConfigCheckResultDTO",
    "CriticScoresDTO",
    "DataInsertsDTO",
    "GoldQueryDTO",
    "GoldResultDTO",
    "JudgeDTO",
    "QuestionDTO",
    "RunMetadataDTO",
    "SchemaDDLDTO",
    "SolverOutputDTO",
    "SpecDTO",
    "StoryDTO",
    "TaskStateDTO",
    "TwistRuleDTO",
]
