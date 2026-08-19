"""Modulo DTO per il linguaggio naturale e le valutazioni.

:author: Riccardo Morabito
"""

from typing import Any

from pydantic import Field, field_validator, model_validator

from bench.domain.models.base import AbstractDTO


class StoryDTO(AbstractDTO):
    """Contesto narrativo del task."""

    story: str = Field(default="", min_length=1)

    @field_validator("story")
    @classmethod
    def validate_story_not_empty(cls, v: str) -> str:
        """Garantisce che la storia generata non sia vuota o composta da soli spazi."""
        cleaned = v.strip()
        if not cleaned:
            msg = "La storia generata non puo' essere vuota o contenere solo spazi."
            raise ValueError(msg)
        return cleaned


class QuestionDTO(AbstractDTO):
    """Domanda finale in linguaggio naturale."""

    question: str = Field(default="", min_length=1)

    @field_validator("question")
    @classmethod
    def validate_question_not_empty(cls, v: str) -> str:
        """Garantisce che la domanda generata non sia vuota o composta da soli spazi."""
        cleaned = v.strip()
        if not cleaned:
            msg = "La domanda generata non puo' essere vuota o contenere solo spazi."
            raise ValueError(msg)
        return cleaned


class CriticScoresDTO(AbstractDTO):
    """Punteggi di qualità assegnati dal Critic."""

    narrative: float = Field(ge=1.0, le=10.0)
    distractors: float = Field(ge=1.0, le=10.0)
    plot_twists: float = Field(ge=1.0, le=10.0)
    jargon: float = Field(ge=1.0, le=10.0)
    sql_composition: float = Field(ge=1.0, le=10.0)

    @model_validator(mode="before")
    @classmethod
    def unwrap_critic(cls, data: Any) -> Any:
        """Estrae l'oggetto annidato 'critic' se l'LLM ha risposto con wrapper."""
        if isinstance(data, dict) and "critic" in data and isinstance(data["critic"], dict):
            return data["critic"]
        return data


class JudgeDTO(AbstractDTO):
    """Verdetto di qualità del Judge."""

    verdict: str = Field(default="hard")

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        """Verifica che il verdetto sia tra i tre valori esatti del contratto."""
        allowed = {"hard", "ambigua", "incompleta"}
        if v not in allowed:
            msg = f"Verdetto '{v}' non valido. Valori esatti ammessi: {sorted(allowed)}"
            raise ValueError(msg)
        return v


class CalibrationResultDTO(AbstractDTO):
    """Dati di calibrazione ed esecuzione del task."""

    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    passes: int = Field(default=0, ge=0)
    first_pass_attempt: int | None = None
    model: str = ""
