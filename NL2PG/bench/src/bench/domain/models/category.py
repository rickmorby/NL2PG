"""Modulo DTO per le categorie di benchmark.

:author: Riccardo Morabito
"""

from pydantic import Field, field_validator
from bench.domain.models.base import AbstractDTO

_MAX_TABLES = 12
_RANGE_LEN = 2


class CategoryDTO(AbstractDTO):
    """Categoria di benchmark validata, caricata da categories.json."""

    descrizione: str = ""
    vincoli: str = ""
    tipo_schema: str = ""
    feature_sql: list[str] = Field(default_factory=list)
    twist_ammessi: list[str] = Field(default_factory=list)
    n_tables_range: list[int] = Field(default_factory=lambda: [1, 5])

    @field_validator("n_tables_range")
    @classmethod
    def _validate_n_tables_range(cls, value: list[int]) -> list[int]:
        """Valida il range [min, max] con 1 <= min <= max <= 12."""
        if len(value) != _RANGE_LEN or not all(isinstance(x, int) for x in value):
            raise ValueError(
                f"n_tables_range deve essere una lista [min, max] di {_RANGE_LEN} interi"
            )
        lo, hi = value
        if not (1 <= lo <= hi <= _MAX_TABLES):
            raise ValueError(
                f"n_tables_range fuori vincoli: atteso 1 <= {lo} <= {hi} <= {_MAX_TABLES}"
            )
        return value
