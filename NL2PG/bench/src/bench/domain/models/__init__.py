"""Modulo package dei modelli DTO per il benchmark sintetico.

:author: Riccardo Morabito
"""

from bench.domain.models.base import AbstractDTO
from bench.domain.models.category import CategoryDTO
from bench.domain.models.document import (
    BatchSummaryDTO,
    BenchmarkTaskDocumentDTO,
    DifficultyDocumentDTO,
    EvaluationDocumentDTO,
    GoldDocumentDTO,
    GoldResultDocumentDTO,
)
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO
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
    "BatchSummaryDTO",
    "CategoryDTO",
    "TwistRuleDTO",
    "SpecDTO",
    "SchemaDDLDTO",
    "DataInsertsDTO",
    "GoldQueryDTO",
    "GoldResultDTO",
    "SolverOutputDTO",
    "StoryDTO",
    "QuestionDTO",
    "CriticScoresDTO",
    "JudgeDTO",
    "CalibrationResultDTO",
    "CallResultDTO",
    "CallOptionsDTO",
    "DifficultyDocumentDTO",
    "GoldResultDocumentDTO",
    "GoldDocumentDTO",
    "EvaluationDocumentDTO",
    "BenchmarkTaskDocumentDTO",
    "TaskStateDTO",
]
