"""Modulo DTO per le specifiche di generazione (Spec e Twist).

:author: Riccardo Morabito
"""

from pydantic import Field
from bench.domain.models.base import AbstractDTO


class TwistRuleDTO(AbstractDTO):
    """Regola per la mutazione di uno schema o dei dati."""

    twist_type: str = ""
    target_value: str = ""
    obsolete_value: str = ""
    description: str = ""


class SpecDTO(AbstractDTO):
    """Specifica per la generazione di uno schema sintetico."""

    domain: str = ""
    n_tables: int = 0
    hierarchy: str = ""
    sql_features: list[str] = Field(default_factory=list)
    twist: list[str] = Field(default_factory=list)
    twist_rules: list[TwistRuleDTO] = Field(default_factory=list)
    spec_hash: str = ""
