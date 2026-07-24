"""Modulo DTO per le chiamate e i failover dei modelli LLM.

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import PrivateAttr
from bench.domain.models.base import AbstractDTO


class FailoverEventDTO(AbstractDTO):
    """Evento di fallback tra modelli LLM."""

    _role: str = PrivateAttr(default="")
    _from_model: str = PrivateAttr(default="")
    _to_model: str = PrivateAttr(default="")
    _reason: str = PrivateAttr(default="")


class CallResultDTO(AbstractDTO):
    """Risposta dall'invocazione di un LLM."""

    _output: Any = PrivateAttr(default=None)
    _model_used: str = PrivateAttr(default="")
    _failovers: list[FailoverEventDTO] = PrivateAttr(default_factory=list)


class CallOptionsDTO(AbstractDTO):
    """Opzioni per la chiamata a un LLM."""

    _force_model: str | None = PrivateAttr(default=None)
    _temperature_override: float | None = PrivateAttr(default=None)
    _error_feedback: str | None = PrivateAttr(default=None)
