"""Modulo DTO per le chiamate e i failover dei modelli LLM.

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import Field
from bench.domain.models.base import AbstractDTO


class FailoverEventDTO(AbstractDTO):
    """Evento di fallback tra modelli LLM."""

    role: str = ""
    from_model: str = ""
    to_model: str = ""
    reason: str = ""


class CallResultDTO(AbstractDTO):
    """Risposta dall'invocazione di un LLM."""

    output: Any = None
    model_used: str = ""
    failovers: list[FailoverEventDTO] = Field(default_factory=list)


class CallOptionsDTO(AbstractDTO):
    """Opzioni per la chiamata a un LLM."""

    force_model: str | None = None
    temperature_override: float | None = None
    error_feedback: str | None = None
