"""Modulo DTO per le categorie di benchmark.

:author: Riccardo Morabito
"""

from pydantic import Field
from bench.domain.models.base import AbstractDTO


class CategoryDTO(AbstractDTO):
    """Categoria di benchmark validata, caricata da categories.json."""

    descrizione: str = ""
    vincoli: str = ""
    tipo_schema: str = ""
    feature_sql: list[str] = Field(default_factory=list)
    twist_ammessi: list[str] = Field(default_factory=list)
