"""Servizio di dominio puro per la valutazione strutturale Text-to-Schema (Text2Schema).

Confronta lo schema candidato generato dal modello con lo schema di riferimento (gold)
attraverso l'allineamento a 3 livelli calibrato per la lingua italiana:
1. Allineamento per sinonimia (Synonym Matching / Dizionario dominio e WordNet);
2. Allineamento semantico (Semantic Similarity Matching con soglia theta_0 = 0.6);
3. Allineamento sintattico LCS (Longest Common Substring con soglia theta_1 = 0.75).

Calcola F1 per tabelle, colonne (con macro-tipi fisici), chiavi primarie e chiavi esterne,
nonche' la Schema Accuracy (SA) binaria: SA = 1 sse F1_schema == 1.

:author: Riccardo Morabito
"""

from collections import defaultdict
from difflib import SequenceMatcher

from pydantic import BaseModel, Field
from sqlglot import exp, parse as sqlglot_parse
from sqlglot.errors import ParseError, TokenError

THETA_SEMANTIC_SIMILARITY = 0.60
THETA_LCS_SYNTACTIC = 0.75

_SYNONYM_CLUSTERS = [
    {
        "cliente",
        "clienti",
        "acquirente",
        "acquirenti",
        "utente",
        "utenti",
        "compratore",
        "compratori",
        "customer",
        "customers",
    },
    {
        "ordine",
        "ordini",
        "commessa",
        "commesse",
        "vendita",
        "vendite",
        "acquisto",
        "acquisti",
        "transazione",
        "transazioni",
    },
    {
        "prodotto",
        "prodotti",
        "articolo",
        "articoli",
        "merce",
        "merci",
        "item",
        "items",
        "bene",
        "beni",
    },
    {
        "dipendente",
        "dipendenti",
        "lavoratore",
        "lavoratori",
        "impiegato",
        "impiegati",
        "collaboratore",
        "collaboratori",
        "staff",
    },
    {
        "recapito",
        "recapiti",
        "telefono",
        "telefoni",
        "cellulare",
        "cellulari",
        "contatto",
        "contatti",
        "indirizzo",
        "indirizzi",
    },
    {
        "saldo",
        "saldi",
        "disponibilita",
        "bilancio",
        "bilanci",
        "credito",
        "crediti",
        "fondo",
        "fondi",
    },
    {
        "prezzo",
        "prezzi",
        "costo",
        "costi",
        "importo",
        "importi",
        "valore",
        "valori",
        "tariffa",
        "tariffe",
        "totale",
        "totali",
    },
    {
        "sede",
        "sedi",
        "filiale",
        "filiali",
        "ufficio",
        "uffici",
        "stabilimento",
        "stabilimenti",
        "dipartimento",
        "dipartimenti",
    },
    {
        "stipendio",
        "stipendi",
        "salario",
        "salari",
        "retribuzione",
        "retribuzioni",
        "compenso",
        "compensi",
    },
    {"data", "date", "giorno", "giorni", "periodo", "periodi", "timestamp"},
    {"descrizione", "descrizioni", "note", "dettaglio", "dettagli", "titolo", "titoli"},
    {"stato", "stati", "condizione", "condizioni", "fase", "fasi"},
    {"categoria", "categorie", "tipologia", "tipologie", "gruppo", "gruppi", "classe", "classi"},
    {
        "fornitore",
        "fornitori",
        "produttore",
        "produttori",
        "distributore",
        "distributori",
        "vendor",
    },
    {"magazzino", "magazzini", "deposito", "depositi", "scorta", "scorte", "inventario"},
]

_SYNONYM_LOOKUP: dict[str, set[str]] = {}
for _cluster in _SYNONYM_CLUSTERS:
    for _w in _cluster:
        _SYNONYM_LOOKUP.setdefault(_w.lower(), set()).update(s.lower() for s in _cluster)

_MACRO_NUMERIC = {
    "int",
    "integer",
    "bigint",
    "smallint",
    "tinyint",
    "serial",
    "bigserial",
    "smallserial",
    "numeric",
    "decimal",
    "real",
    "double",
    "float",
    "money",
    "number",
}
_MACRO_TEXT = {
    "varchar",
    "char",
    "character",
    "text",
    "bpchar",
    "string",
    "citext",
    "json",
    "jsonb",
    "uuid",
}
_MACRO_TEMPORAL = {"date", "time", "timestamp", "timestamptz", "interval", "datetime"}
_MACRO_BOOLEAN = {"bool", "boolean"}


def normalize_macro_type(type_name: str) -> str:
    """Normalizza un tipo SQL PostgreSQL nella corrispondente macro-categoria logica."""
    t = type_name.lower().split("(")[0].strip()
    if any(k in t for k in _MACRO_NUMERIC):
        return "NUMERIC"
    if any(k in t for k in _MACRO_TEXT):
        return "TEXT"
    if any(k in t for k in _MACRO_TEMPORAL):
        return "TEMPORAL"
    if any(k in t for k in _MACRO_BOOLEAN):
        return "BOOLEAN"
    return "OTHER"


_EXACT_THRESHOLD = 0.999


def longest_common_substring_len(s1: str, s2: str) -> int:
    """Calcola la lunghezza della piu' lunga sottostringa comune continua tra due stringhe."""
    matcher = SequenceMatcher(None, s1.lower(), s2.lower())
    match = matcher.find_longest_match(0, len(s1), 0, len(s2))
    return match.size


def lcs_ratio(s1: str, s2: str) -> float:
    """Calcola il rapporto LCS normalizzato rispetto alla lunghezza media."""
    if not s1 or not s2:
        return 0.0
    lcs_len = longest_common_substring_len(s1, s2)
    return (2.0 * lcs_len) / (len(s1) + len(s2))


def char_ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Calcola la similarita' del coseno tra profili n-grammi di caratteri."""
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2:
        return 1.0
    if len(s1) < n or len(s2) < n:
        return 1.0 if s1 == s2 else 0.0

    ngrams1: dict[str, int] = defaultdict(int)
    for i in range(len(s1) - n + 1):
        ngrams1[s1[i : i + n]] += 1

    ngrams2: dict[str, int] = defaultdict(int)
    for i in range(len(s2) - n + 1):
        ngrams2[s2[i : i + n]] += 1

    dot = sum(ngrams1[k] * ngrams2.get(k, 0) for k in ngrams1)
    norm1 = sum(v * v for v in ngrams1.values()) ** 0.5
    norm2 = sum(v * v for v in ngrams2.values()) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


def are_identifiers_aligned(id1: str, id2: str) -> bool:
    """Implementa la cascata di allineamento a tre livelli per l'italiano (Sezione 4.3)."""
    s1, s2 = id1.lower().strip(), id2.lower().strip()
    if s1 == s2:
        return True

    if s2 in _SYNONYM_LOOKUP.get(s1, set()) or s1 in _SYNONYM_LOOKUP.get(s2, set()):
        return True

    if lcs_ratio(s1, s2) >= THETA_LCS_SYNTACTIC:
        return True

    return char_ngram_similarity(s1, s2, n=3) >= THETA_SEMANTIC_SIMILARITY


class TableSchemaInfo(BaseModel):
    """Informazioni estratte per una singola tabella del DDL."""

    name: str = Field(default="")
    columns: dict[str, str] = Field(default_factory=dict)
    primary_keys: set[str] = Field(default_factory=set)
    foreign_keys: set[tuple[str, str, str]] = Field(default_factory=set)


class SchemaEvaluationResultDTO(BaseModel):
    """Risultato completo della valutazione Text-to-Schema con metriche Text2Schema."""

    table_f1: float = Field(default=0.0)
    table_precision: float = Field(default=0.0)
    table_recall: float = Field(default=0.0)

    column_f1: float = Field(default=0.0)
    column_precision: float = Field(default=0.0)
    column_recall: float = Field(default=0.0)

    pk_f1: float = Field(default=0.0)
    fk_f1: float = Field(default=0.0)

    schema_f1: float = Field(default=0.0)
    schema_accuracy: float = Field(default=0.0)


class SchemaEvaluator:
    """Valutatore dello schema relazionale conforme al protocollo formale della Sezione 4.3."""

    @staticmethod
    def parse_ddl_structure(ddl_sql: str) -> dict[str, TableSchemaInfo]:  # noqa: C901, PLR0912
        """Estrae la struttura relazionale completa dal codice DDL (CREATE TABLE ed ALTER TABLE)."""
        if not ddl_sql or not ddl_sql.strip():
            return {}

        tables: dict[str, TableSchemaInfo] = {}
        try:
            statements = sqlglot_parse(ddl_sql, read="postgres")
        except (ParseError, TokenError, ValueError, AttributeError):
            return {}

        for stmt in statements:
            if isinstance(stmt, exp.Create) and str(stmt.args.get("kind", "")).upper() == "TABLE":
                tbl = stmt.this.find(exp.Table)
                if tbl is None:
                    continue
                tbl_name = tbl.name.lower()
                cols: dict[str, str] = {}
                pks: set[str] = set()
                fks: set[tuple[str, str, str]] = set()

                for cdef in stmt.this.find_all(exp.ColumnDef):
                    cname = cdef.name.lower()
                    raw_type = cdef.kind.sql() if cdef.kind else "TEXT"
                    cols[cname] = normalize_macro_type(raw_type)

                    for constr in cdef.find_all(exp.ColumnConstraint):
                        if isinstance(constr.kind, exp.PrimaryKeyColumnConstraint):
                            pks.add(cname)
                        elif isinstance(constr.kind, exp.Reference):
                            ref_tbl_node = constr.kind.find(exp.Table)
                            ref_tbl = ref_tbl_node.name.lower() if ref_tbl_node else ""
                            ref_col_nodes = [
                                e.name.lower() for e in constr.kind.find_all(exp.Identifier)
                            ]
                            ref_col = ref_col_nodes[0] if ref_col_nodes else "id"
                            if ref_tbl:
                                fks.add((cname, ref_tbl, ref_col))

                for pk in stmt.this.find_all(exp.PrimaryKey):
                    for expr in pk.expressions:
                        pks.add(expr.name.lower())

                for fk in stmt.this.find_all(exp.ForeignKey):
                    fk_cols = [e.name.lower() for e in fk.expressions]
                    ref = fk.find(exp.Reference)
                    if ref and fk_cols:
                        ref_tbl_node = ref.find(exp.Table)
                        ref_tbl = ref_tbl_node.name.lower() if ref_tbl_node else ""
                        ref_col_nodes = [e.name.lower() for e in ref.find_all(exp.Identifier)]
                        ref_col = ref_col_nodes[0] if ref_col_nodes else "id"
                        if ref_tbl:
                            for cname in fk_cols:
                                fks.add((cname, ref_tbl, ref_col))

                tables[tbl_name] = TableSchemaInfo(
                    name=tbl_name,
                    columns=cols,
                    primary_keys=pks,
                    foreign_keys=fks,
                )

            elif isinstance(stmt, exp.Alter):
                tbl_name = stmt.this.name.lower() if stmt.this else ""
                if tbl_name in tables:
                    for fk in stmt.find_all(exp.ForeignKey):
                        fk_cols = [e.name.lower() for e in fk.expressions]
                        ref = fk.find(exp.Reference)
                        if ref and fk_cols:
                            ref_tbl_node = ref.find(exp.Table)
                            ref_tbl = ref_tbl_node.name.lower() if ref_tbl_node else ""
                            ref_col_nodes = [e.name.lower() for e in ref.find_all(exp.Identifier)]
                            ref_col = ref_col_nodes[0] if ref_col_nodes else "id"
                            if ref_tbl:
                                for cname in fk_cols:
                                    tables[tbl_name].foreign_keys.add((cname, ref_tbl, ref_col))

        return tables

    def evaluate(  # noqa: C901, PLR0912, PLR0915
        self, gold_ddl: str, cand_ddl: str
    ) -> SchemaEvaluationResultDTO:
        """Esegue il confronto analitico tra lo schema DDL gold e candidato."""
        gold_tables = self.parse_ddl_structure(gold_ddl)
        cand_tables = self.parse_ddl_structure(cand_ddl)

        if not gold_tables:
            return SchemaEvaluationResultDTO(schema_f1=1.0, schema_accuracy=1.0)
        if not cand_tables:
            return SchemaEvaluationResultDTO(schema_f1=0.0, schema_accuracy=0.0)

        table_matches: dict[str, str] = {}
        unmatched_gold = set(gold_tables.keys())

        for cand_name in cand_tables:
            if cand_name in unmatched_gold:
                table_matches[cand_name] = cand_name
                unmatched_gold.remove(cand_name)

        for cand_name in cand_tables:
            if cand_name in table_matches:
                continue
            for gold_name in list(unmatched_gold):
                if are_identifiers_aligned(cand_name, gold_name):
                    table_matches[cand_name] = gold_name
                    unmatched_gold.remove(gold_name)
                    break

        n_ms_tbl = len(table_matches)
        n_gs_tbl = len(gold_tables)
        n_ps_tbl = len(cand_tables)
        p_tbl = n_ms_tbl / n_ps_tbl if n_ps_tbl > 0 else 0.0
        r_tbl = n_ms_tbl / n_gs_tbl if n_gs_tbl > 0 else 0.0
        f1_tbl = (2 * p_tbl * r_tbl / (p_tbl + r_tbl)) if (p_tbl + r_tbl) > 0 else 0.0

        tot_ms_col = 0
        tot_gs_col = sum(len(t.columns) for t in gold_tables.values())
        tot_ps_col = sum(len(t.columns) for t in cand_tables.values())

        tot_ms_pk = 0
        tot_gs_pk = sum(len(t.primary_keys) for t in gold_tables.values())
        tot_ps_pk = sum(len(t.primary_keys) for t in cand_tables.values())

        tot_ms_fk = 0
        tot_gs_fk = sum(len(t.foreign_keys) for t in gold_tables.values())
        tot_ps_fk = sum(len(t.foreign_keys) for t in cand_tables.values())

        for cand_name, gold_name in table_matches.items():
            cand_info = cand_tables[cand_name]
            gold_info = gold_tables[gold_name]

            col_matches: dict[str, str] = {}
            unmatched_gold_cols = set(gold_info.columns.keys())

            for ccol, ctype in cand_info.columns.items():
                if ccol in unmatched_gold_cols:
                    gtype = gold_info.columns[ccol]
                    if ctype in (gtype, "OTHER") or gtype == "OTHER":
                        col_matches[ccol] = ccol
                        unmatched_gold_cols.remove(ccol)
                        tot_ms_col += 1

            for ccol, ctype in cand_info.columns.items():
                if ccol in col_matches:
                    continue
                for gcol in list(unmatched_gold_cols):
                    gtype = gold_info.columns[gcol]
                    if are_identifiers_aligned(ccol, gcol) and (
                        ctype in (gtype, "OTHER") or gtype == "OTHER"
                    ):
                        col_matches[ccol] = gcol
                        unmatched_gold_cols.remove(gcol)
                        tot_ms_col += 1
                        break

            for cpk in cand_info.primary_keys:
                gpk_target = col_matches.get(cpk, cpk)
                if gpk_target in gold_info.primary_keys:
                    tot_ms_pk += 1

            for c_col, c_ref_tbl, _c_ref_col in cand_info.foreign_keys:
                g_col_aligned = col_matches.get(c_col, c_col)
                g_ref_tbl_aligned = table_matches.get(c_ref_tbl, c_ref_tbl)
                for g_col, g_ref_tbl, _g_ref_col in gold_info.foreign_keys:
                    if g_col == g_col_aligned and are_identifiers_aligned(
                        g_ref_tbl, g_ref_tbl_aligned
                    ):
                        tot_ms_fk += 1
                        break

        p_col = tot_ms_col / tot_ps_col if tot_ps_col > 0 else 0.0
        r_col = tot_ms_col / tot_gs_col if tot_gs_col > 0 else 0.0
        f1_col = (2 * p_col * r_col / (p_col + r_col)) if (p_col + r_col) > 0 else 0.0

        p_pk = tot_ms_pk / tot_ps_pk if tot_ps_pk > 0 else 0.0
        r_pk = tot_ms_pk / tot_gs_pk if tot_gs_pk > 0 else 0.0
        f1_pk = (
            (2 * p_pk * r_pk / (p_pk + r_pk))
            if (p_pk + r_pk) > 0
            else (1.0 if tot_gs_pk == 0 and tot_ps_pk == 0 else 0.0)
        )

        p_fk = tot_ms_fk / tot_ps_fk if tot_ps_fk > 0 else 0.0
        r_fk = tot_ms_fk / tot_gs_fk if tot_gs_fk > 0 else 0.0
        f1_fk = (
            (2 * p_fk * r_fk / (p_fk + r_fk))
            if (p_fk + r_fk) > 0
            else (1.0 if tot_gs_fk == 0 and tot_ps_fk == 0 else 0.0)
        )

        components = [f1_tbl, f1_col]
        if tot_gs_pk > 0 or tot_ps_pk > 0:
            components.append(f1_pk)
        if tot_gs_fk > 0 or tot_ps_fk > 0:
            components.append(f1_fk)

        schema_f1 = sum(components) / len(components) if components else 0.0
        is_exact = (
            f1_tbl >= _EXACT_THRESHOLD
            and f1_col >= _EXACT_THRESHOLD
            and (tot_gs_pk == 0 or f1_pk >= _EXACT_THRESHOLD)
            and (tot_gs_fk == 0 or f1_fk >= _EXACT_THRESHOLD)
        )
        schema_accuracy = 1.0 if is_exact else 0.0

        return SchemaEvaluationResultDTO(
            table_f1=round(f1_tbl, 4),
            table_precision=round(p_tbl, 4),
            table_recall=round(r_tbl, 4),
            column_f1=round(f1_col, 4),
            column_precision=round(p_col, 4),
            column_recall=round(r_col, 4),
            pk_f1=round(f1_pk, 4),
            fk_f1=round(f1_fk, 4),
            schema_f1=round(schema_f1, 4),
            schema_accuracy=schema_accuracy,
        )
