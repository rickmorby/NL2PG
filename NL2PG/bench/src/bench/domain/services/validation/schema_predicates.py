"""Predicatori dei marcatori DDL per tipo di schema.

Ogni funzione risponde alla domanda: il DDL presenta il costrutto strutturale
atteso dal ``tipo_schema`` della categoria?

:author: Riccardo Morabito
"""

from re import IGNORECASE
from re import compile as re_compile, escape as re_escape

from sqlglot import exp

from bench.domain.services.validation.ddl_introspection import collect_pk_fk, get_all_creates
from bench.domain.services.validation.ddl_markers import (  # noqa: F401
    _DENORMALIZED_MARKERS,
    _DENORMALIZED_MARKERS_RE,
    _MIN_COMPOSITE_FK,
    _MIN_FACT_FK,
    _RE_AUDIT_COLUMN,
    _RE_COLUMN_FK,
    _RE_COMPOSITE_TYPE,
    _RE_CREATE_DOMAIN,
    _RE_CREATE_TABLE,
    _RE_DEFAULT_NOW,
    _RE_DENORMALIZED_COLUMN,
    _RE_ENUM_TYPE,
    _RE_EXCLUSIVE_CHECK,
    _RE_GENERATED_ALWAYS,
    _RE_NOT_NULL,
    _RE_ON_ACTION,
    _RE_PARTITION_BY,
    _RE_RANGE_COLUMN,
    _RE_RANGE_TYPE,
    _RE_SOFT_DELETE_COLUMN,
    _RE_TABLE_LEVEL_FK,
    _RE_TEMPORAL_COLUMN,
)




def has_partition_by(ddl: str) -> bool:
    """Verifica la presenza della clausola PARTITION BY."""
    return bool(_RE_PARTITION_BY.search(ddl))


def has_composite_type(ddl: str) -> bool:
    """Verifica la presenza di un CREATE TYPE ... AS (...) composito."""
    return bool(_RE_COMPOSITE_TYPE.search(ddl))


def has_generated_always(ddl: str) -> bool:
    """Verifica la presenza di una colonna GENERATED ALWAYS AS (...)."""
    return bool(_RE_GENERATED_ALWAYS.search(ddl))


def has_enum_type(ddl: str) -> bool:
    """Verifica la presenza di un CREATE TYPE ... AS ENUM (...)."""
    return bool(_RE_ENUM_TYPE.search(ddl))


def has_range_type(ddl: str) -> bool:
    """Verifica la presenza di tipi range (colonna o CREATE TYPE AS RANGE)."""
    return bool(_RE_RANGE_COLUMN.search(ddl) or _RE_RANGE_TYPE.search(ddl))


def has_on_action(ddl: str) -> bool:
    """Verifica la presenza di azioni referenziali ON DELETE / ON UPDATE."""
    return bool(_RE_ON_ACTION.search(ddl))


def has_self_fk(ddl: str) -> bool:
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


def has_audit_columns(ddl: str) -> bool:
    """Verifica la presenza di colonne di audit o DEFAULT CURRENT_TIMESTAMP."""
    return bool(_RE_AUDIT_COLUMN.search(ddl) or _RE_DEFAULT_NOW.search(ddl))


def has_nullable_fk(ddl: str) -> bool:
    """Verifica la presenza di almeno una colonna REFERENCES senza NOT NULL."""
    for stmt in ddl.split(";"):
        without_table_fk = _RE_TABLE_LEVEL_FK.sub("", stmt)
        for _col_name, col_def in _RE_COLUMN_FK.findall(without_table_fk):
            if not _RE_NOT_NULL.search(col_def):
                return True
    return False


def has_soft_deletion(ddl: str) -> bool:
    """Verifica la presenza di una colonna di soft delete."""
    return bool(_RE_SOFT_DELETE_COLUMN.search(ddl))


def has_temporal_columns(ddl: str) -> bool:
    """Verifica la presenza di colonne di validita' temporale."""
    return bool(_RE_TEMPORAL_COLUMN.search(ddl))


def has_denormalized_column(ddl: str) -> bool:
    """Verifica la presenza di colonne ridondanti o derivate (denormalizzazione)."""
    return bool(_RE_DENORMALIZED_COLUMN.search(ddl))


def has_create_domain(ddl: str) -> bool:
    """Verifica la presenza di CREATE DOMAIN (vincoli di dominio)."""
    return bool(_RE_CREATE_DOMAIN.search(ddl))


def has_weak_entity_pk(ddl: str) -> bool:
    """Verifica una tabella la cui PK composta include la colonna FK del proprietario."""
    for create in get_all_creates(ddl):
        pk_cols, fk_cols = collect_pk_fk(create)
        if len(pk_cols) >= _MIN_COMPOSITE_FK and (pk_cols & fk_cols):
            return True
    return False


def has_isa_tables(ddl: str) -> bool:
    """Verifica il pattern ISA: tabella figlia con PK che e' anche FK verso il padre."""
    for create in get_all_creates(ddl):
        pk_single: str | None = None
        fk_target: str | None = None
        for cd in create.find_all(exp.ColumnDef):
            is_pk = any(
                isinstance(s.kind, exp.PrimaryKeyColumnConstraint)
                for s in cd.find_all(exp.ColumnConstraint)
            )
            ref = next(
                (
                    s
                    for s in cd.find_all(exp.ColumnConstraint)
                    if isinstance(s.kind, exp.Reference)
                ),
                None,
            )
            if is_pk and ref is not None:
                pk_single = cd.name.lower()
                this = ref.kind.args.get("this")
                tbl = this.find(exp.Table) if this is not None else None
                fk_target = tbl.name.lower() if tbl else None
        if pk_single and fk_target:
            return True
    return False


def has_junction_table(ddl: str) -> bool:
    """Verifica una tabella ponte: due o piu' FK che compongono la chiave primaria."""
    for create in get_all_creates(ddl):
        fk_cols: set[str] = set()
        pk_cols: list[str] = []
        for cd in create.find_all(exp.ColumnDef):
            for spec in cd.find_all(exp.ColumnConstraint):
                if isinstance(spec.kind, exp.Reference):
                    fk_cols.add(cd.name.lower())
                if isinstance(spec.kind, exp.PrimaryKeyColumnConstraint):
                    pk_cols.append(cd.name.lower())
        for ft in create.find_all(exp.ForeignKey):
            fk_cols.update(
                e.name.lower()
                for e in ft.expressions
                if isinstance(e, (exp.Column, exp.Identifier))
            )
        for cons in create.find_all(exp.PrimaryKey):
            pk_cols.extend(
                e.name.lower()
                for e in cons.expressions
                if isinstance(e, (exp.Column, exp.Identifier))
            )
        if len(fk_cols) >= _MIN_COMPOSITE_FK and fk_cols.issubset(set(pk_cols)):
            return True
    return False


def has_fact_table(ddl: str) -> bool:
    """Verifica una tabella dei fatti con almeno due FK verso dimensioni."""
    for create in get_all_creates(ddl):
        fk_cols: set[str] = set()
        for cd in create.find_all(exp.ColumnDef):
            if any(
                isinstance(s.kind, exp.Reference) for s in cd.find_all(exp.ColumnConstraint)
            ):
                fk_cols.add(cd.name.lower())
        for ft in create.find_all(exp.ForeignKey):
            fk_cols.update(
                e.name.lower()
                for e in ft.expressions
                if isinstance(e, (exp.Column, exp.Identifier))
            )
        if len(fk_cols) >= _MIN_FACT_FK:
            return True
    return False


def has_exclusive_arcs(ddl: str) -> bool:
    """Verifica archi esclusivi: piu' FK nullable piu' CHECK di esclusivita' IS NULL."""
    if not _RE_EXCLUSIVE_CHECK.search(ddl):
        return False
    refs = 0
    for create in get_all_creates(ddl):
        for cd in create.find_all(exp.ColumnDef):
            has_ref = any(
                isinstance(s.kind, exp.Reference) for s in cd.find_all(exp.ColumnConstraint)
            )
            if has_ref:
                nulls = [
                    s
                    for s in cd.find_all(exp.ColumnConstraint)
                    if isinstance(s.kind, exp.NotNullColumnConstraint)
                ]
                if not nulls:
                    refs += 1
        for _ft in create.find_all(exp.ForeignKey):
            refs += 1
    return refs >= _MIN_FACT_FK
