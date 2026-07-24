"""Modulo package dei modelli DTO per il benchmark sintetico.

:author: Riccardo Morabito
"""

from bench.models.base import DTOInterface, AbstractDTO
from bench.models.category import RawCategoryDTO, CategoryDraftDTO, CategoryDTO
from bench.models.spec import TwistRuleDTO, SpecDTO
from bench.models.sql import (
    SchemaDDLDTO,
    DataInsertsDTO,
    GoldQueryDTO,
    GoldResultDTO,
    SolverOutputDTO,
)
from bench.models.nlp import (
    StoryDTO,
    QuestionDTO,
    CriticScoresDTO,
    JudgeDTO,
    CalibrationResultDTO,
)
from bench.models.llm import FailoverEventDTO, CallResultDTO, CallOptionsDTO
from bench.models.document import (
    DifficultyDocumentDTO,
    GoldResultDocumentDTO,
    GoldDocumentDTO,
    EvaluationDocumentDTO,
    BenchmarkTaskDocumentDTO,
)
from bench.models.state import TaskStateDTO

__all__ = [
    "DTOInterface",
    "AbstractDTO",
    "RawCategoryDTO",
    "CategoryDraftDTO",
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
    "FailoverEventDTO",
    "CallResultDTO",
    "CallOptionsDTO",
    "DifficultyDocumentDTO",
    "GoldResultDocumentDTO",
    "GoldDocumentDTO",
    "EvaluationDocumentDTO",
    "BenchmarkTaskDocumentDTO",
    "TaskStateDTO",
]
