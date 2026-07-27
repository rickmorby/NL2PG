"""Modulo DTO per le categorie di benchmark.

:author: Riccardo Morabito
"""

from pydantic import Field
from bench.domain.models.base import AbstractDTO


class CategoryDTO(AbstractDTO):
    """Categoria di benchmark validata, caricata da categories.json."""

    id: str = ""
    descrizione: str = ""
    vincoli: str = ""
    tipo_schema: str = ""
    feature_sql: list[str] = Field(default_factory=list)
    twist_ammessi: list[str] = Field(default_factory=list)
    composizioni: list[str] = Field(default_factory=list)
    query_type_ids: list[int] = Field(default_factory=list)
    schema_type_ids: list[int] = Field(default_factory=list)
    esempi_sql: list[str] = Field(default_factory=list)
    logical_pattern: str = ""
    instructions: str = ""
    query_type: str = ""
    schema_type: str = ""
