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

from sqlglot import exp, parse
from sqlglot.errors import ParseError

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
_DENORMALIZED_MARKERS: tuple[str, ...] = (
    "totale",
    "totali",
    "tot",
    "somma",
    "somme",
    "sommi",
    "subtotale",
    "subtotali",
    "totalizz",
    "saldo",
    "saldi",
    "residuo",
    "residua",
    "residui",
    "residue",
    "rimanenza",
    "rimanenze",
    "eccedenza",
    "eccedenze",
    "conteggio",
    "conteggi",
    "numero",
    "numeri",
    "num",
    "n",
    "importo",
    "importi",
    "imp",
    "valore",
    "valori",
    "val",
    "giacenza",
    "giacenze",
    "netto",
    "netta",
    "netti",
    "nette",
    "medio",
    "media",
    "medi",
    "medie",
    "cumulativo",
    "cumulativa",
    "cumulativi",
    "cumulate",
    "cumulato",
    "cumulata",
    "accumulato",
    "accumulata",
    "accumulati",
    "accumulate",
    "punteggio",
    "punteggi",
    "punti",
    "rating",
    "consumato",
    "consumata",
    "consumati",
    "consumate",
    "utilizzato",
    "utilizzata",
    "utilizzati",
    "utilizzate",
    "impegnato",
    "impegnata",
    "impegnati",
    "impegnate",
    "arpu",
    "traffico",
    "ammortamento",
    "ammortamenti",
    "consuntivo",
    "consuntiva",
    "consuntivi",
    "consuntive",
    "progressivo",
    "progressiva",
    "progressivi",
    "progressive",
    "calcolato",
    "calcolata",
    "calcolati",
    "calcolate",
    "derivato",
    "derivata",
    "derivati",
    "derivate",
    "riportato",
    "riportata",
    "riportati",
    "riportate",
    "variazione",
    "variazioni",
    "aggregato",
    "aggregata",
    "aggregati",
    "aggregate",
    "totalizzato",
    "totalizzata",
)
_DENORMALIZED_MARKERS_RE = "|".join(_DENORMALIZED_MARKERS)
_MIN_COMPOSITE_FK = 2
_MIN_FACT_FK = 2

_RE_CREATE_DOMAIN = re_compile(r"^\s*CREATE\s+DOMAIN\b", IGNORECASE)
_RE_EXCLUSIVE_CHECK = re_compile(
    r"CHECK\s*\([\s\S]*?(?:IS\s+(?:NOT\s+)?NULL|num_nonnulls|\bCASE\b|<>|=)[\s\S]*?\)",
    flags=IGNORECASE,
)
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
    r"(?:^|[,(]\s*)(?:" + _DENORMALIZED_MARKERS_RE + r")(?:_[a-z0-9]+)*\s+"
    r"(?:TEXT|NUMERIC|INT|INTEGER|BIGINT|SMALLINT|REAL|DOUBLE|DECIMAL|BOOLEAN)",
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
    def _collect_pk_fk(create: exp.Create) -> tuple[set[str], set[str]]:
        """Raccoglie colonne PK e FK di una CREATE TABLE (livello colonna e tabella)."""
        pk_cols: set[str] = set()
        fk_cols: set[str] = set()
        for cd in create.find_all(exp.ColumnDef):
            for spec in cd.find_all(exp.ColumnConstraint):
                if isinstance(spec.kind, exp.PrimaryKeyColumnConstraint):
                    pk_cols.add(cd.name.lower())
                if isinstance(spec.kind, exp.Reference):
                    fk_cols.add(cd.name.lower())
        for cons in create.find_all(exp.PrimaryKey):
            pk_cols.update(
                e.name.lower()
                for e in cons.expressions
                if isinstance(e, (exp.Column, exp.Identifier))
            )
        for ft in create.find_all(exp.ForeignKey):
            fk_cols.update(
                e.name.lower()
                for e in ft.expressions
                if isinstance(e, (exp.Column, exp.Identifier))
            )
        return pk_cols, fk_cols

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

    @staticmethod
    def _has_create_domain(ddl: str) -> bool:
        """Verifica la presenza di CREATE DOMAIN (vincoli di dominio)."""
        return bool(_RE_CREATE_DOMAIN.search(ddl))

    @staticmethod
    def _get_all_creates(ddl: str) -> list[exp.Create]:
        """Estrae tutte le istruzioni CREATE TABLE dal DDL multi-statement."""
        try:
            trees = parse(ddl, read="postgres")
            creates = []
            for t in trees:
                if t:
                    if isinstance(t, exp.Create):
                        creates.append(t)
                    creates.extend(t.find_all(exp.Create))
            return list(dict.fromkeys(creates))
        except (ParseError, ValueError, AttributeError):
            return []

    @staticmethod
    def _has_weak_entity_pk(ddl: str) -> bool:
        """Verifica una tabella la cui PK composta include la colonna FK del proprietario."""
        for create in SchemaTypeChecker._get_all_creates(ddl):
            pk_cols, fk_cols = SchemaTypeChecker._collect_pk_fk(create)
            if len(pk_cols) >= _MIN_COMPOSITE_FK and (pk_cols & fk_cols):
                return True
        return False

    @staticmethod
    def _has_isa_tables(ddl: str) -> bool:
        """Verifica il pattern ISA: tabella figlia con PK che e' anche FK verso il padre."""
        for create in SchemaTypeChecker._get_all_creates(ddl):
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

    @staticmethod
    def _has_junction_table(ddl: str) -> bool:
        """Verifica una tabella ponte: due o piu' FK che compongono la chiave primaria."""
        for create in SchemaTypeChecker._get_all_creates(ddl):
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

    @staticmethod
    def _has_fact_table(ddl: str) -> bool:
        """Verifica una tabella dei fatti con almeno due FK verso dimensioni."""
        for create in SchemaTypeChecker._get_all_creates(ddl):
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

    @staticmethod
    def _has_exclusive_arcs(ddl: str) -> bool:
        """Verifica archi esclusivi: piu' FK nullable piu' CHECK di esclusivita' IS NULL."""
        if not _RE_EXCLUSIVE_CHECK.search(ddl):
            return False
        refs = 0
        for create in SchemaTypeChecker._get_all_creates(ddl):
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
        "domain_constraint": _has_create_domain,
        "weak_entity": _has_weak_entity_pk,
        "isa": _has_isa_tables,
        "associative_entity": _has_junction_table,
        "many_to_many": _has_junction_table,
        "dimensional_modeling": _has_fact_table,
        "polymorphic": _has_exclusive_arcs,
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
