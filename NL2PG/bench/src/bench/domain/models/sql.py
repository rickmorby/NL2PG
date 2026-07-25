"""Modulo DTO per componenti SQL e dati.

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import Field
from bench.domain.models.base import AbstractDTO


class SchemaDDLDTO(AbstractDTO):
    """Script DDL per la creazione dello schema."""

    ddl: str = ""


class DataInsertsDTO(AbstractDTO):
    """Istruzioni INSERT per i dati sintetici."""

    inserts: str = ""


class GoldQueryDTO(AbstractDTO):
    """Query SQL Gold di riferimento."""

    query: str = ""
    intent: str = ""
    order_sensitive: bool = False


class GoldResultDTO(AbstractDTO):
    """Risultato dell'esecuzione della query Gold."""

    columns: list[str] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    order_sensitive: bool = False


class SolverOutputDTO(AbstractDTO):
    """Query generata da un solver in esame."""

    query: str = ""
