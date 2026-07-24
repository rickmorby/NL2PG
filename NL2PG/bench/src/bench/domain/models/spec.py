"""Modulo DTO per le specifiche di generazione (Spec e Twist).

:author: Riccardo Morabito
"""

from pydantic import PrivateAttr
from bench.domain.models.base import AbstractDTO


class TwistRuleDTO(AbstractDTO):
    """Regola per la mutazione di uno schema o dei dati."""

    _twist_type: str = PrivateAttr(default="")
    _target_value: str = PrivateAttr(default="")
    _obsolete_value: str = PrivateAttr(default="")
    _description: str = PrivateAttr(default="")


class SpecDTO(AbstractDTO):
    """Specifica per la generazione di uno schema sintetico."""

    _domain: str = PrivateAttr(default="")
    _n_tables: int = PrivateAttr(default=0)
    _hierarchy: str = PrivateAttr(default="")
    _sql_features: list[str] = PrivateAttr(default_factory=list)
    _twist: list[str] = PrivateAttr(default_factory=list)
    _twist_rules: list[TwistRuleDTO] = PrivateAttr(default_factory=list)
    _spec_hash: str = PrivateAttr(default="")
