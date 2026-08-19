"""Modulo DTO per le specifiche di generazione (Spec e Twist).

:author: Riccardo Morabito
"""

from pydantic import Field
from bench.domain.models.base import AbstractDTO


class TwistRuleDTO(AbstractDTO):
    """Regola per la mutazione di uno schema o dei dati."""

    twist_type: str = Field(default="")
    target_value: str = Field(default="")
    obsolete_value: str = Field(default="")
    description: str = Field(default="")


class SpecDTO(AbstractDTO):
    """Specifica per la generazione di uno schema sintetico."""

    domain: str = Field(default="")
    n_tables: int = Field(default=1, ge=1, le=12)
    hierarchy: str = Field(default="")
    sql_features: list[str] = Field(default_factory=list)
    twist: list[str] = Field(default_factory=list)
    twist_rules: list[TwistRuleDTO] = Field(default_factory=list)
    spec_hash: str = Field(default="")
