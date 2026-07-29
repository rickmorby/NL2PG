"""Modulo DTO per il linguaggio naturale e le valutazioni.

:author: Riccardo Morabito
"""

from pydantic import Field, field_validator

from bench.domain.models.base import AbstractDTO


class StoryDTO(AbstractDTO):
    """Contesto narrativo del task."""

    story: str = Field(default="", min_length=1)


class QuestionDTO(AbstractDTO):
    """Domanda finale in linguaggio naturale."""

    question: str = Field(default="", min_length=1)


class CriticScoresDTO(AbstractDTO):
    """Punteggi di qualità assegnati dal Critic."""

    narrative: float = Field(default=1.0, ge=1.0, le=10.0)
    distractors: float = Field(default=1.0, ge=1.0, le=10.0)
    plot_twists: float = Field(default=1.0, ge=1.0, le=10.0)
    jargon: float = Field(default=1.0, ge=1.0, le=10.0)
    sql_composition: float = Field(default=1.0, ge=1.0, le=10.0)


class JudgeDTO(AbstractDTO):
    """Verdetto di qualità del Judge."""

    verdict: str = Field(default="hard")

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        """Verifica che il verdetto sia tra i tre valori esatti di contratto."""
        allowed = {"hard", "ambigua", "incompleta"}
        if v not in allowed:
            msg = f"Verdetto '{v}' non valido. Deve essere uno tra i valori esatti del contratto: {sorted(allowed)}"
            raise ValueError(msg)
        return v


class CalibrationResultDTO(AbstractDTO):
    """Dati di calibrazione ed esecuzione del task."""

    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    passes: int = Field(default=0, ge=0)
    runs: int = Field(default=0, ge=0)
    first_pass_attempt: int | None = None
    model: str = ""
