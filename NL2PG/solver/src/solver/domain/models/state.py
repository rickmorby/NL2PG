"""DTO per lo stato transitorio di un task durante l'esecuzione del solver.

:author: Riccardo Morabito
"""

from typing import Any

from pydantic import Field, field_validator

from solver.domain.models.base import AbstractDTO


class SolverTaskStateDTO(AbstractDTO):
    """Stato di lavorazione di un task nel runner del solver."""

    task_id: str = Field(default="")
    category: str = Field(default="")
    domain: str = Field(default="")
    n_tables: int = Field(default=1)
    hierarchy: str = Field(default="")
    spec_hash: str = Field(default="")
    sql_features: list[str] = Field(default_factory=list)
    twists: list[str] = Field(default_factory=list)
    twist_rules: list[dict[str, Any]] = Field(default_factory=list)
    difficulty_label: str = Field(default="hard")
    critic_score: float = Field(default=0.0)
    calibration_pass_rate: float = Field(default=0.0)
    story: str = Field(default="")
    question: str = Field(default="")

    gold_schema_ddl: str = Field(default="")
    gold_data_inserts: str = Field(default="")
    gold_query: str = Field(default="")
    gold_rows: list[list[Any]] = Field(default_factory=list)
    gold_columns: list[str] = Field(default_factory=list)
    order_sensitive: bool = Field(default=False)
    datalog_scale: int = Field(default=1000)

    sandbox_schema: str = Field(default="")
    generated_schema_ddl: str | None = Field(default=None)

    @field_validator("gold_data_inserts", mode="before")
    @classmethod
    def _normalize_inserts(cls, val: Any) -> str:
        """Normalizza la lista di INSERT o stringa in una stringa SQL univoca."""
        if isinstance(val, list):
            return "\n".join(str(v).strip() for v in val if v)
        if isinstance(val, str):
            return val
        return "" if val is None else str(val)

    @field_validator("gold_schema_ddl", "gold_query", "story", "question", mode="before")
    @classmethod
    def _normalize_strings(cls, val: Any) -> str:
        """Normalizza campi testuali."""
        if isinstance(val, str):
            return val
        return "" if val is None else str(val)

    @field_validator("gold_rows", mode="before")
    @classmethod
    def _normalize_rows(cls, val: Any) -> list[list[Any]]:
        """Normalizza le righe della query gold in lista di liste."""
        if not val:
            return []
        if isinstance(val, list):
            return [list(r) if isinstance(r, (list, tuple)) else [r] for r in val]
        return []
