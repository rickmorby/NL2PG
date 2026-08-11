"""Modulo DTO per le chiamate ed i controlli di diagnosi dei modelli LLM e configurazioni.

:author: Riccardo Morabito
"""

from typing import Any

from pydantic import Field

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


class ConfigCheckResultDTO(AbstractDTO):
    """Esito del controllo di integrità delle configurazioni del sistema."""

    bench_loaded: bool = True
    models_count: int = 0
    categories_count: int = 0
    config_hash: str = ""
    categories_hash: str = ""


class ModelHealthDTO(AbstractDTO):
    """Esito della diagnosi per un singolo modello LLM."""

    model_id: str
    target_model: str = ""
    roles: list[str] = Field(default_factory=list)
    is_available_on_server: bool = False
    is_healthy: bool = False
    error_message: str = ""


class ProviderHealthDTO(AbstractDTO):
    """Esito della diagnosi per un singolo provider LLM."""

    provider_name: str
    base_url: str
    is_reachable: bool = False
    error_message: str = ""
    models: list[ModelHealthDTO] = Field(default_factory=list)


class SystemHealthReportDTO(AbstractDTO):
    """Report globale di salute di tutti i provider e modelli configurati."""

    total_providers: int = 0
    reachable_providers: int = 0
    total_models: int = 0
    healthy_models: int = 0
    providers: list[ProviderHealthDTO] = Field(default_factory=list)
