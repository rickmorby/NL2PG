"""Modulo DTO per le categorie di benchmark.

:author: Riccardo Morabito
"""

from pydantic import Field
from bench.domain.models.base import AbstractDTO


class RawCategoryDTO(AbstractDTO):
    """Categoria grezza letta da file Markdown."""

    id: str = ""
    title: str = ""
    content: str = ""
    sql_examples: list[str] = Field(default_factory=list)


class CategoryDraftDTO(AbstractDTO):
    """Bozza di categoria generata dall'LLM."""

    name: str = ""
    description: str = ""
    sql_features: list[str] = Field(default_factory=list)
    schema_type: str = ""
    compositions: list[str] = Field(default_factory=list)
    allowed_twists: list[str] = Field(default_factory=list)
    constraints: str = ""


class CategoryDTO(AbstractDTO):
    """Categoria validata per il benchmark."""

    id: str = ""
    name: str = ""
    description: str = ""
    sql_features: list[str] = Field(default_factory=list)
    schema_type: str = ""
    compositions: list[str] = Field(default_factory=list)
    allowed_twists: list[str] = Field(default_factory=list)
    constraints: str = ""
    sql_examples: list[str] = Field(default_factory=list)
