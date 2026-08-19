"""Modelli di dominio per lo schema relazionale e la specifica di generazione dati.

:author: Riccardo Morabito
"""

from typing import Any, Literal

from pydantic import Field, model_validator

from bench.domain.models.base import AbstractDTO


class ColumnSchema:
    """Metadati di una colonna estratti dallo schema relazionale (information_schema)."""

    def __init__(
        self,
        name: str,
        data_type: str,
        nullable: bool,
        is_pk: bool = False,
        is_fk: bool = False,
        is_unique: bool = False,
        fk_parent_table: str | None = None,
        fk_parent_column: str | None = None,
    ) -> None:
        """Inizializza i metadati della colonna."""
        self.name = name
        self.data_type = data_type
        self.nullable = nullable
        self.is_pk = is_pk
        self.is_fk = is_fk
        self.is_unique = is_unique
        self.fk_parent_table = fk_parent_table
        self.fk_parent_column = fk_parent_column


class TableSchema:
    """Metadati di una tabella: colonne, chiavi primarie ed esterne."""

    def __init__(
        self,
        name: str,
        columns: list[ColumnSchema],
        unique_groups: list[list[str]] | None = None,
    ) -> None:
        """Inizializza i metadati della tabella e deriva PK, FK e UNIQUE."""
        self.name = name
        self.columns = columns
        self.pk_columns: list[str] = [c.name for c in columns if c.is_pk]
        self.fk_columns: list[ColumnSchema] = [c for c in columns if c.is_fk]
        self.unique_groups: list[list[str]] = unique_groups or []

    def column(self, name: str) -> ColumnSchema | None:
        """Restituisce la colonna per nome o None se assente."""
        return next((c for c in self.columns if c.name == name), None)


class SchemaModel:
    """Modello dello schema relazionale con tabelle indicizzate per nome."""

    def __init__(self, tables: list[TableSchema]) -> None:
        """Indicizza le tabelle per nome normalizzato (lowercase)."""
        self.tables: dict[str, TableSchema] = {t.name.lower(): t for t in tables}

    def table(self, name: str) -> TableSchema | None:
        """Restituisce la tabella per nome normalizzato o None se assente."""
        return self.tables.get(name.lower())


class ColumnVariationDTO(AbstractDTO):
    """Asse di variazione di una colonna rispetto al valore del template."""

    axis: Literal["fixed", "shift", "scale", "pool"] = "fixed"
    delta_min: float | None = None
    delta_max: float | None = None
    factor_min: float | None = None
    factor_max: float | None = None
    pool: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_pool_values(self) -> "ColumnVariationDTO":
        """Verifica che l'asse pool abbia almeno un valore candidato."""
        if self.axis == "pool" and not self.pool:
            raise ValueError("Asse 'pool' richiede una lista di valori")
        return self


class TableDataSpecDTO(AbstractDTO):
    """Specifica di generazione per una singola tabella."""

    table: str = ""
    nature: Literal["lookup", "dimension", "fact", "explicit"] = "dimension"
    min_rows: int | None = None
    max_rows: int | None = None
    per_parent_rows: float | None = None
    templates: list[dict[str, Any]] = Field(default_factory=list, min_length=1)
    variations: dict[str, ColumnVariationDTO] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_explicit_range(self) -> "TableDataSpecDTO":
        """Verifica che la natura explicit dichiari un range valido."""
        if self.nature == "explicit" and (self.min_rows is None or self.max_rows is None):
            raise ValueError("Natura 'explicit' richiede min_rows e max_rows")
        if (
            self.min_rows is not None
            and self.max_rows is not None
            and self.min_rows > self.max_rows
        ):
            raise ValueError("Range non valido: min > max")
        return self


class DataSpecDTO(AbstractDTO):
    """Specifica di generazione dati per l'intero schema (una voce per tabella)."""

    tables: list[TableDataSpecDTO] = Field(default_factory=list)


class DataProfileDTO(AbstractDTO):
    """Profilo dati deterministico mostrato agli agenti a valle (query, story, critic).

    ``profile`` contiene statistiche compatte per tabella (conteggi, valori
    distinti, min/max, campioni); ``preview`` contiene le prime righe reali
    generate (stesso seed -> stesse righe) cosi' gli agenti scrivono filtri su
    valori realmente presenti nel database.
    """

    profile: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
