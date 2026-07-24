"""Modulo DTO per il documento finale del benchmark in YAML.

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import PrivateAttr
from bench.models.base import AbstractDTO


class DifficultyDocumentDTO(AbstractDTO):
    """Difficoltà del task per l'esportazione."""

    _label: str = PrivateAttr(default="")
    _critic_score: float | None = PrivateAttr(default=None)
    _calibration_pass_rate: float | None = PrivateAttr(default=None)
    _calibration_model: str = PrivateAttr(default="")


class GoldResultDocumentDTO(AbstractDTO):
    """Risultato Gold per l'esportazione."""

    _columns: list[str] = PrivateAttr(default_factory=list)
    _rows: list[Any] = PrivateAttr(default_factory=list)
    _order_sensitive: bool = PrivateAttr(default=False)


class GoldDocumentDTO(AbstractDTO):
    """Insieme di schema, dati, query e risultato Gold."""

    _schema_ddl: str = PrivateAttr(default="")
    _data_inserts: str = PrivateAttr(default="")
    _query: str = PrivateAttr(default="")
    _result: GoldResultDocumentDTO | None = PrivateAttr(default=None)


class EvaluationDocumentDTO(AbstractDTO):
    """Parametri per la valutazione del benchmark."""

    _schema_matching: str = PrivateAttr(default="normalized_names")
    _result_comparison: str = PrivateAttr(default="bag_semantics")


class BenchmarkTaskDocumentDTO(AbstractDTO):
    """Documento completo del task per l'esportazione in YAML."""

    _id: str = PrivateAttr(default="")
    _version: int = PrivateAttr(default=1)
    _language: str = PrivateAttr(default="it")
    _category: str = PrivateAttr(default="")
    _spec: dict[str, Any] | None = PrivateAttr(default=None)
    _difficulty: DifficultyDocumentDTO = PrivateAttr(default_factory=DifficultyDocumentDTO)
    _story: str = PrivateAttr(default="")
    _question: str = PrivateAttr(default="")
    _gold: GoldDocumentDTO = PrivateAttr(default_factory=GoldDocumentDTO)
    _evaluation: EvaluationDocumentDTO = PrivateAttr(default_factory=EvaluationDocumentDTO)
