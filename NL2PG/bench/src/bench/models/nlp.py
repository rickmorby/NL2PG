"""Modulo DTO per il linguaggio naturale e le valutazioni.

:author: Riccardo Morabito
"""

from pydantic import PrivateAttr
from bench.models.base import AbstractDTO


class StoryDTO(AbstractDTO):
    """Contesto narrativo del task."""

    _story: str = PrivateAttr(default="")


class QuestionDTO(AbstractDTO):
    """Domanda finale in linguaggio naturale."""

    _question: str = PrivateAttr(default="")


class CriticScoresDTO(AbstractDTO):
    """Punteggi di qualità assegnati dal Critic."""

    _narrative: float = PrivateAttr(default=0.0)
    _distractors: float = PrivateAttr(default=0.0)
    _plot_twists: float = PrivateAttr(default=0.0)
    _jargon: float = PrivateAttr(default=0.0)
    _sql_composition: float = PrivateAttr(default=0.0)


class JudgeDTO(AbstractDTO):
    """Verdetto di qualità del Judge."""

    _verdict: str = PrivateAttr(default="hard")


class CalibrationResultDTO(AbstractDTO):
    """Dati di calibrazione ed esecuzione del task."""

    _pass_rate: float = PrivateAttr(default=0.0)
    _passes: int = PrivateAttr(default=0)
    _runs: int = PrivateAttr(default=0)
    _first_pass_attempt: int | None = PrivateAttr(default=None)
    _model: str = PrivateAttr(default="")
