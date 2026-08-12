"""Modulo DTO per le metriche ed analisi statistiche del benchmark.

:author: Riccardo Morabito
"""

from pydantic import Field

from bench.domain.models.base import AbstractDTO


class AnalyticsDTO(AbstractDTO):
    """DTO per le metriche ed aggregati statistici scientifici di una run."""

    run_id: str = ""
    generated_at: str = ""
    total_tasks: int = 0
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    domain_distribution: dict[str, int] = Field(default_factory=dict)
    sql_feature_counts: dict[str, int] = Field(default_factory=dict)
    twist_type_counts: dict[str, int] = Field(default_factory=dict)
    avg_critic_scores: dict[str, float] = Field(default_factory=dict)
    avg_pass_rate: float = 0.0
    plots_count: int = 0
