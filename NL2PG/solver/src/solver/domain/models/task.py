"""Modelli dati del task del benchmark, allineati al formato promosso dal bench.

Il solver e' un progetto indipendente: la struttura rispecchia il contratto del
benchmark JSON (``task_id``, ``spec``, ``difficulty``, ``gold``) senza alcuna
dipendenza dal progetto bench.

:author: Riccardo Morabito
"""

from typing import Any

from pydantic import Field, field_validator

from solver.domain.models.base import AbstractDTO


class TaskSpecDTO(AbstractDTO):
    """Specifica generativa del task."""

    domain: str = Field(default="")
    hierarchy: str = Field(default="")
    n_tables: int = Field(default=1)
    spec_hash: str = Field(default="")
    sql_features: list[str] = Field(default_factory=list)
    twist: list[str] = Field(default_factory=list)
    twist_rules: list[dict[str, Any]] = Field(default_factory=list)


class TaskDifficultyDTO(AbstractDTO):
    """Metadati di difficolta' e calibrazione del task."""

    label: str = Field(default="hard")
    critic_score: float = Field(default=0.0)
    calibration_pass_rate: float = Field(default=0.0)
    calibration_model: str = Field(default="")


class TaskGoldResultDTO(AbstractDTO):
    """Risultato atteso della gold query."""

    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    order_sensitive: bool = Field(default=False)


class TaskGoldDTO(AbstractDTO):
    """Artefatti gold del task: schema, dati, query e risultato."""

    schema_ddl: str = Field(default="")
    data_inserts: str = Field(default="")
    data_spec: dict[str, Any] = Field(default_factory=dict)
    data_profile: dict[str, Any] = Field(default_factory=dict)
    query: str = Field(default="")
    result: TaskGoldResultDTO = Field(default_factory=TaskGoldResultDTO)

    @field_validator("data_inserts", mode="before")
    @classmethod
    def _normalize_inserts(cls, val: Any) -> str:
        """Normalizza lista di INSERT o stringa in un unico script SQL."""
        if isinstance(val, list):
            return "\n".join(str(item).strip() for item in val if item)
        if isinstance(val, str):
            return val
        return "" if val is None else str(val)


class TaskDTO(AbstractDTO):
    """Radice del task del benchmark nel nuovo formato."""

    task_id: str = Field(default="")
    category: str = Field(default="")
    story: str = Field(default="")
    question: str = Field(default="")
    spec: TaskSpecDTO = Field(default_factory=TaskSpecDTO)
    difficulty: TaskDifficultyDTO = Field(default_factory=TaskDifficultyDTO)
    gold: TaskGoldDTO = Field(default_factory=TaskGoldDTO)
