"""Modulo servizio di dominio per la verifica del tipo di schema richiesto nel DDL.

Il servizio verifica che lo script DDL presenti il marcatore strutturale atteso per il
``tipo_schema`` dichiarato dalla categoria (es. ``partitioned`` -> ``PARTITION BY``).
I tipi senza marcatore DDL verificabile meccanicamente (naming, pattern relazionali
strutturali) non vengono controllati e passano senza vincoli.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from re import IGNORECASE, compile as re_compile, escape as re_escape
from typing import Callable, ClassVar

_RE_PARTITION_BY = re_compile(r"\bPARTITION\s+BY\b", IGNORECASE)
_RE_COMPOSITE_TYPE = re_compile(r"CREATE\s+TYPE\s+[\w\"]+\s+AS\s*\(", IGNORECASE)
_RE_GENERATED_ALWAYS = re_compile(r"\bGENERATED\s+ALWAYS\s+AS\s*\(", IGNORECASE)
_RE_ENUM_TYPE = re_compile(r"CREATE\s+TYPE\s+[\w\"]+\s+AS\s+ENUM\s*\(", IGNORECASE)
_RE_RANGE_COLUMN = re_compile(
    r"\b(?:tsrange|tstzrange|daterange|int4range|int8range|numrange)\b", IGNORECASE
)
_RE_RANGE_TYPE = re_compile(r"CREATE\s+TYPE\s+[\w\"]+\s+AS\s+RANGE\b", IGNORECASE)
_RE_ON_ACTION = re_compile(r"\bON\s+(?:DELETE|UPDATE)\b", IGNORECASE)
_RE_AUDIT_COLUMN = re_compile(
    r"\b(?:created_at|created_by|updated_at|updated_by|inserted_at|modified_at|"
    r"last_modified|creato_il|modificato_il|creato_da|modificato_da)\b",
    IGNORECASE,
)
_RE_DEFAULT_NOW = re_compile(r"\bDEFAULT\s+CURRENT_TIMESTAMP\b", IGNORECASE)
_RE_SOFT_DELETE_COLUMN = re_compile(
    r"\b(?:deleted_at|is_deleted|data_eliminazione|is_active|eliminato|cancellato)\b",
    IGNORECASE,
)
_RE_TEMPORAL_COLUMN = re_compile(
    r"\b(?:valid_from|valid_to|data_inizio|data_fine|effective_from|effective_to|"
    r"periodo_dal|periodo_al|valido_dal|valido_al)\b",
    IGNORECASE,
)
_RE_DENORMALIZED_COLUMN = re_compile(
    r"\b(?:totale_|tot_|saldo_|subtotale_|conteggio_|n_ordini|numero_ordini)\w*",
    IGNORECASE,
)
_RE_CREATE_TABLE = re_compile(r"CREATE\s+TABLE\s+[\w\"]+", IGNORECASE)
_RE_TABLE_LEVEL_FK = re_compile(
    r"FOREIGN\s+KEY\s*\([^)]*\)\s*REFERENCES\s+[\w\"]+\s*\([^)]*\)", IGNORECASE
)
_RE_COLUMN_FK = re_compile(
    r"([\w\"]+)\s+([^\n;]+?)\s+REFERENCES\s+[\w\"]+\s*\(",
    IGNORECASE,
)
_RE_NOT_NULL = re_compile(r"\bNOT\s+NULL\b", IGNORECASE)


@dataclass
class SchemaTypeCheckResult:
    """Esito della verifica del tipo di schema richiesto nel DDL."""

    is_valid: bool = True
    error: str = ""


class SchemaTypeChecker:
    """Servizio di dominio per la verifica dei marcatori DDL del tipo di schema."""

    @staticmethod
    def _has_partition_by(ddl: str) -> bool:
        """Verifica la presenza della clausola PARTITION BY."""
        return bool(_RE_PARTITION_BY.search(ddl))

    @staticmethod
    def _has_composite_type(ddl: str) -> bool:
        """Verifica la presenza di un CREATE TYPE ... AS (...) composito."""
        return bool(_RE_COMPOSITE_TYPE.search(ddl))

    @staticmethod
    def _has_generated_always(ddl: str) -> bool:
        """Verifica la presenza di una colonna GENERATED ALWAYS AS (...)."""
        return bool(_RE_GENERATED_ALWAYS.search(ddl))

    @staticmethod
    def _has_enum_type(ddl: str) -> bool:
        """Verifica la presenza di un CREATE TYPE ... AS ENUM (...)."""
        return bool(_RE_ENUM_TYPE.search(ddl))

    @staticmethod
    def _has_range_type(ddl: str) -> bool:
        """Verifica la presenza di tipi range (colonna o CREATE TYPE AS RANGE)."""
        return bool(_RE_RANGE_COLUMN.search(ddl) or _RE_RANGE_TYPE.search(ddl))

    @staticmethod
    def _has_on_action(ddl: str) -> bool:
        """Verifica la presenza di azioni referenziali ON DELETE / ON UPDATE."""
        return bool(_RE_ON_ACTION.search(ddl))

    @staticmethod
    def _has_self_fk(ddl: str) -> bool:
        """Verifica che una tabella referenzi se stessa con REFERENCES."""
        for stmt in ddl.split(";"):
            match = _RE_CREATE_TABLE.search(stmt)
            if not match:
                continue
            table = match.group(0).split()[-1].strip('"')
            pattern = re_compile(rf"REFERENCES\s+[\"\']?{re_escape(table)}[\"\']?\b", IGNORECASE)
            if pattern.search(stmt):
                return True
        return False

    @staticmethod
    def _has_audit_columns(ddl: str) -> bool:
        """Verifica la presenza di colonne di audit o DEFAULT CURRENT_TIMESTAMP."""
        return bool(_RE_AUDIT_COLUMN.search(ddl) or _RE_DEFAULT_NOW.search(ddl))

    @staticmethod
    def _has_nullable_fk(ddl: str) -> bool:
        """Verifica la presenza di almeno una colonna REFERENCES senza NOT NULL."""
        for stmt in ddl.split(";"):
            without_table_fk = _RE_TABLE_LEVEL_FK.sub("", stmt)
            for _col_name, col_def in _RE_COLUMN_FK.findall(without_table_fk):
                if not _RE_NOT_NULL.search(col_def):
                    return True
        return False

    @staticmethod
    def _has_soft_deletion(ddl: str) -> bool:
        """Verifica la presenza di una colonna di soft delete."""
        return bool(_RE_SOFT_DELETE_COLUMN.search(ddl))

    @staticmethod
    def _has_temporal_columns(ddl: str) -> bool:
        """Verifica la presenza di colonne di validita' temporale."""
        return bool(_RE_TEMPORAL_COLUMN.search(ddl))

    @staticmethod
    def _has_denormalized_column(ddl: str) -> bool:
        """Verifica la presenza di colonne ridondanti o derivate (denormalizzazione)."""
        return bool(_RE_DENORMALIZED_COLUMN.search(ddl))

    _CHECKS: ClassVar[dict[str, Callable[[str], bool]]] = {
        "partitioned": _has_partition_by,
        "composite_column": _has_composite_type,
        "generated_columns": _has_generated_always,
        "enum_type": _has_enum_type,
        "range_type": _has_range_type,
        "referential_action": _has_on_action,
        "self_referencing": _has_self_fk,
        "audit_columns": _has_audit_columns,
        "optional_fk": _has_nullable_fk,
        "soft_deletion": _has_soft_deletion,
        "temporal_modeling": _has_temporal_columns,
        "denormalized": _has_denormalized_column,
    }

    _HINTS: ClassVar[dict[str, str]] = {
        "partitioned": (
            "la clausola PARTITION BY (es. CREATE TABLE ... PARTITION BY RANGE (colonna))"
        ),
        "composite_column": (
            "CREATE TYPE nome AS (col1 TIPO, col2 TIPO) e una colonna di quel tipo composito"
        ),
        "generated_columns": "una colonna GENERATED ALWAYS AS (espressione) STORED",
        "enum_type": "CREATE TYPE nome AS ENUM ('val1', 'val2')",
        "range_type": (
            "una colonna di tipo range (es. daterange, tsrange) oppure CREATE TYPE ... AS RANGE"
        ),
        "referential_action": "un vincolo FK con ON DELETE o ON UPDATE",
        "self_referencing": (
            "una FK che REFERENCES la stessa tabella (es. manager_id REFERENCES dipendenti(id))"
        ),
        "audit_columns": (
            "colonne di audit (es. created_at, updated_at, creato_il) o DEFAULT CURRENT_TIMESTAMP"
        ),
        "optional_fk": "almeno una colonna FK nullable (REFERENCES senza NOT NULL)",
        "soft_deletion": "una colonna di soft delete (es. deleted_at, is_deleted, eliminato)",
        "temporal_modeling": (
            "colonne di validita' temporale (es. valid_from, valid_to, data_inizio, data_fine)"
        ),
        "denormalized": "una colonna ridondante o derivata (es. totale_speso, saldo, n_ordini)",
    }

    def check(self, ddl: str, tipo_schema: str) -> SchemaTypeCheckResult:
        """Verifica che il DDL presenti il marcatore del tipo di schema richiesto."""
        if not tipo_schema or tipo_schema not in self._CHECKS:
            return SchemaTypeCheckResult()
        if self._CHECKS[tipo_schema](ddl):
            return SchemaTypeCheckResult()
        hint = self._HINTS.get(tipo_schema, "il costrutto DDL atteso")
        error = (
            f"Lo schema DDL non rispetta il tipo di schema richiesto '{tipo_schema}': manca {hint}."
        )
        return SchemaTypeCheckResult(is_valid=False, error=error)

    @classmethod
    def known_types(cls) -> frozenset[str]:
        """Restituisce il vocabolario dei tipi di schema verificabili via DDL."""
        return frozenset(cls._CHECKS)
