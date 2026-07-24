"""Modulo package dei modelli DTO per il benchmark sintetico.

:author: Riccardo Morabito
"""

from bench.domain.models.base import DTOInterface, AbstractDTO
from bench.domain.models.category import RawCategoryDTO, CategoryDraftDTO, CategoryDTO
from bench.domain.models.spec import TwistRuleDTO, SpecDTO
from bench.domain.models.sql import (
    SchemaDDLDTO,
    DataInsertsDTO,
    GoldQueryDTO,
    GoldResultDTO,
    SolverOutputDTO,
)
from bench.domain.models.nlp import (
    StoryDTO,
    QuestionDTO,
    CriticScoresDTO,
    JudgeDTO,
    CalibrationResultDTO,
)
from bench.domain.models.llm import FailoverEventDTO, CallResultDTO, CallOptionsDTO
from bench.domain.models.document import (
    DifficultyDocumentDTO,
    GoldResultDocumentDTO,
    GoldDocumentDTO,
    EvaluationDocumentDTO,
    BenchmarkTaskDocumentDTO,
)
from bench.domain.models.state import TaskStateDTO

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
