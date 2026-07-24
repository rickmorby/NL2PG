"""Modulo DTO per le categorie di benchmark.

:author: Riccardo Morabito
"""

from pydantic import PrivateAttr
from bench.models.base import AbstractDTO


class RawCategoryDTO(AbstractDTO):
    """Categoria grezza letta da file Markdown."""

    _id: str = PrivateAttr(default="")
    _title: str = PrivateAttr(default="")
    _content: str = PrivateAttr(default="")
    _sql_examples: list[str] = PrivateAttr(default_factory=list)


class CategoryDraftDTO(AbstractDTO):
    """Bozza di categoria generata dall'LLM."""

    _name: str = PrivateAttr(default="")
    _description: str = PrivateAttr(default="")
    _sql_features: list[str] = PrivateAttr(default_factory=list)
    _schema_type: str = PrivateAttr(default="")
    _compositions: list[str] = PrivateAttr(default_factory=list)
    _allowed_twists: list[str] = PrivateAttr(default_factory=list)
    _constraints: str = PrivateAttr(default="")


class CategoryDTO(AbstractDTO):
    """Categoria validata per il benchmark."""

    _id: str = PrivateAttr(default="")
    _name: str = PrivateAttr(default="")
    _description: str = PrivateAttr(default="")
    _sql_features: list[str] = PrivateAttr(default_factory=list)
    _schema_type: str = PrivateAttr(default="")
    _compositions: list[str] = PrivateAttr(default_factory=list)
    _allowed_twists: list[str] = PrivateAttr(default_factory=list)
    _constraints: str = PrivateAttr(default="")
    _sql_examples: list[str] = PrivateAttr(default_factory=list)
