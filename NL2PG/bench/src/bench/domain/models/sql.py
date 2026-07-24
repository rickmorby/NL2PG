"""Modulo DTO per componenti SQL e dati.

:author: Riccardo Morabito
"""

from pydantic import PrivateAttr
from bench.domain.models.base import AbstractDTO


class SchemaDDLDTO(AbstractDTO):
    """Script DDL per la creazione dello schema."""

    _ddl: str = PrivateAttr(default="")


class DataInsertsDTO(AbstractDTO):
    """Istruzioni INSERT per i dati sintetici."""

    _inserts: str = PrivateAttr(default="")


class GoldQueryDTO(AbstractDTO):
    """Query SQL Gold di riferimento."""

    _query: str = PrivateAttr(default="")
    _intent: str = PrivateAttr(default="")
    _order_sensitive: bool = PrivateAttr(default=False)


class GoldResultDTO(AbstractDTO):
    """Risultato dell'esecuzione della query Gold."""

    _columns: list[str] = PrivateAttr(default_factory=list)
    _rows: list[str] = PrivateAttr(default_factory=list)
    _order_sensitive: bool = PrivateAttr(default=False)


class SolverOutputDTO(AbstractDTO):
    """Query generata da un solver in esame."""

    _query: str = PrivateAttr(default="")
