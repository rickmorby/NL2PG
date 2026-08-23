"""Lessico dei marcatori DDL per i tipi di schema.

Regex compilate e liste chiuse di termini riconosciuti; condivise verbatim
con i prompt di generazione (schema.txt): aggiungere un marcatore QUI lo
dichiara anche nel contratto verso l'LLM.

:author: Riccardo Morabito
"""

from re import IGNORECASE
from re import compile as re_compile

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
