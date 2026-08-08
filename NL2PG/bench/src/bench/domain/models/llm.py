"""Modulo DTO per le chiamate ai modelli LLM.

:author: Riccardo Morabito
"""

from typing import Any
from bench.domain.models.base import AbstractDTO


class CallResultDTO(AbstractDTO):
    """Risposta dall'invocazione di un LLM."""

    output: Any = None
    model_used: str = ""


class CallOptionsDTO(AbstractDTO):
    """Opzioni per la chiamata a un LLM."""

    force_model: str | None = None
    temperature_override: float | None = None
    error_feedback: str | None = None


class HealthCheckDTO(AbstractDTO):
    """DTO diagnostico leggero per i test di connettività dei provider LLM."""

    status: str = "ok"

