"""Modulo DTO per le metriche ed analisi statistiche scientifiche del solver.

:author: Riccardo Morabito
"""

from typing import Any

from pydantic import Field

from solver.domain.models.base import AbstractDTO


class ContingencyMatrixDTO(AbstractDTO):
    """Matrice di contingenza a 4 quadranti per l'asimmetria Schema vs Query."""

    q11_both_success: int = 0
    q10_schema_ok_query_fail: int = 0
    q01_schema_fail_query_ok: int = 0
    q00_both_fail: int = 0

    @property
    def total(self) -> int:
        """Restituisce il numero totale di task classificati nella matrice."""
        return (
            self.q11_both_success
            + self.q10_schema_ok_query_fail
            + self.q01_schema_fail_query_ok
            + self.q00_both_fail
        )


class SolverAnalyticsDTO(AbstractDTO):
    """DTO radice per tutti gli aggregati statistici e scientifici di una run del solver."""

    run_id: str = ""
    generated_at: str = ""
    total_tasks: int = 0
    model_name: str = ""

    schema_accuracy: float = 0.0
    schema_gap: float = 0.0
    query_gold_accuracy: float = 0.0
    query_generated_accuracy: float = 0.0
    end_to_end_accuracy: float = 0.0
    cascade_error_delta: float = 0.0

    contingency_matrix: ContingencyMatrixDTO = Field(default_factory=ContingencyMatrixDTO)
    recipe_accuracies: dict[str, float] = Field(default_factory=dict)
    error_rates_by_sql_feature: dict[str, float] = Field(default_factory=dict)
    error_rates_by_twist_type: dict[str, float] = Field(default_factory=dict)
    accuracy_by_twist_count: dict[int, float] = Field(default_factory=dict)
    accuracy_by_domain: dict[str, float] = Field(default_factory=dict)
    accuracy_by_table_count: dict[int, float] = Field(default_factory=dict)
    error_taxonomy_counts: dict[str, int] = Field(default_factory=dict)
    rag_boost_by_twist: dict[str, float] = Field(default_factory=dict)
    plots_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
