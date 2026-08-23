"""Servizio di verifica del tipo di schema richiesto nel DDL.

Mappa ogni ``tipo_schema`` del catalogo categorie al predicato che ne riconosce
il marcatore strutturale nel DDL e agli hint per la correzione.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from typing import Callable, ClassVar

from bench.domain.services.validation.schema_predicates import (
    has_audit_columns,
    has_composite_type,
    has_create_domain,
    has_denormalized_column,
    has_enum_type,
    has_exclusive_arcs,
    has_fact_table,
    has_generated_always,
    has_isa_tables,
    has_junction_table,
    has_nullable_fk,
    has_on_action,
    has_partition_by,
    has_range_type,
    has_self_fk,
    has_soft_deletion,
    has_temporal_columns,
    has_weak_entity_pk,
)


@dataclass
class SchemaTypeCheckResult:
    """Esito della verifica del tipo di schema richiesto nel DDL."""

    is_valid: bool = True
    error: str = ""


class SchemaTypeChecker:
    """Servizio di dominio per la verifica dei marcatori DDL del tipo di schema."""

    _CHECKS: ClassVar[dict[str, Callable[[str], bool]]] = {
        "partitioned": has_partition_by,
        "composite_column": has_composite_type,
        "generated_columns": has_generated_always,
        "enum_type": has_enum_type,
        "range_type": has_range_type,
        "referential_action": has_on_action,
        "self_referencing": has_self_fk,
        "audit_columns": has_audit_columns,
        "optional_fk": has_nullable_fk,
        "soft_deletion": has_soft_deletion,
        "temporal_modeling": has_temporal_columns,
        "denormalized": has_denormalized_column,
        "domain_constraint": has_create_domain,
        "weak_entity": has_weak_entity_pk,
        "isa": has_isa_tables,
        "associative_entity": has_junction_table,
        "many_to_many": has_junction_table,
        "dimensional_modeling": has_fact_table,
        "polymorphic": has_exclusive_arcs,
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
        "denormalized": (
            "una colonna derivata o ridondante il cui nome contiene uno dei termini "
            "di aggregazione previsti (es. totale_speso NUMERIC, saldo_contabile NUMERIC, "
            "n_ordini INT, importo_residuo NUMERIC, valore_stock NUMERIC, giacenza_disponibile INT)"
        ),
        "domain_constraint": "CREATE DOMAIN nome AS tipo CHECK (VALUE IN (...) o altra condizione)",
        "weak_entity": (
            "una tabella la cui PRIMARY KEY composta include la colonna FK del proprietario "
            "(es. PRIMARY KEY (fattura_id, numero_riga))"
        ),
        "isa": (
            "una tabella figlia la cui PK e' anche FK verso la tabella padre "
            "(es. id INT PRIMARY KEY REFERENCES dipendenti(id))"
        ),
        "associative_entity": (
            "una tabella ponte con due o piu' colonne FK "
            "(es. studente_id REFERENCES studenti(id), corso_id REFERENCES corsi(id))"
        ),
        "many_to_many": ("una tabella ponte con doppia FK che risolve la relazione N:N"),
        "dimensional_modeling": (
            "una tabella dei fatti con almeno due FK verso tabelle dimensione (star schema)"
        ),
        "polymorphic": (
            "due o piu' FK nullable con un CHECK che impone esattamente una valorizzata "
            "(es. CHECK ((cliente_id IS NULL) <> (fornitore_id IS NULL)))"
        ),
    }

    @staticmethod
    def check(ddl: str, tipo_schema: str) -> SchemaTypeCheckResult:
        """Verifica che il DDL presenti il marcatore del tipo di schema richiesto."""
        if not tipo_schema or tipo_schema not in SchemaTypeChecker._CHECKS:
            return SchemaTypeCheckResult()
        if SchemaTypeChecker._CHECKS[tipo_schema](ddl):
            return SchemaTypeCheckResult()
        hint = SchemaTypeChecker._HINTS.get(tipo_schema, "il costrutto DDL atteso")
        error = (
            f"Lo schema DDL non rispetta il tipo di schema richiesto '{tipo_schema}': manca {hint}."
        )
        return SchemaTypeCheckResult(is_valid=False, error=error)
