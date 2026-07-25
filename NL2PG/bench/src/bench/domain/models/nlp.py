"""Modulo DTO per il linguaggio naturale e le valutazioni.

:author: Riccardo Morabito
"""

from bench.domain.models.base import AbstractDTO


class StoryDTO(AbstractDTO):
    """Contesto narrativo del task."""

    story: str = ""


class QuestionDTO(AbstractDTO):
    """Domanda finale in linguaggio naturale."""

    question: str = ""


class CriticScoresDTO(AbstractDTO):
    """Punteggi di qualità assegnati dal Critic."""

    narrative: float = 0.0
    distractors: float = 0.0
    plot_twists: float = 0.0
    jargon: float = 0.0
    sql_composition: float = 0.0


class JudgeDTO(AbstractDTO):
    """Verdetto di qualità del Judge."""

    verdict: str = "hard"


class CalibrationResultDTO(AbstractDTO):
    """Dati di calibrazione ed esecuzione del task."""

    pass_rate: float = 0.0
    passes: int = 0
    runs: int = 0
    first_pass_attempt: int | None = None
    model: str = ""
