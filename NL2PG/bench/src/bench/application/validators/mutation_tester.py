"""Modulo validatore applicativo per il mutation testing su query SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from random import choice, shuffle
from typing import Any
from datetime import date, timedelta
from psycopg import sql
from psycopg.errors import Error as PgError, ForeignKeyViolation
from sqlglot import parse_one, exp
from bench.domain.ports.outbound.database_port import DatabasePort

_MUTATABLE_TYPES = frozenset({
    "integer", "bigint", "smallint",
    "numeric", "decimal", "real", "double precision",
    "text", "character varying", "char", "character",
    "boolean", "date", "timestamp without time zone",
    "timestamp with time zone", "timestamp",
})


@dataclass
class MutationResult:
    """Esito del test di mutazione su una query SQL."""

    is_valid: bool = True
    error: str = ""


class MutationTester:
    """Validatore applicativo che verifica la sensibilita' di una query SQL a mutazioni dei dati."""

    def __init__(self, db: DatabasePort):
        """Inizializza il tester con la porta database per l'accesso al sandbox."""
        self._db = db

    def test(
        self, schema: str, query: str, tables: list[str], attempts: int = 3
    ) -> MutationResult:
        """Testa se la query e' sensibile a mutazioni dei dati nel sandbox."""
        if not tables:
            return MutationResult()
        with self._db.get_sandbox_connection(schema) as conn:
            with conn.cursor() as cur:
                base_tables = self._base_tables(cur)
                targets = [t for t in tables if t in base_tables]
                if not targets:
                    return MutationResult()
                is_agg = self._is_scalar_aggregate(query)
                mutatable = self._filter_mutatable(cur, targets, query)
                if not is_agg and not mutatable:
                    return MutationResult(
                        is_valid=False,
                        error="nessuna colonna mutabile usata e query non aggregata",
                    )
                orig_rows = self._safe_query(cur, conn, query)
                if orig_rows is None:
                    return MutationResult(
                        is_valid=False, error="esecuzione query fallita durante test mutazione"
                    )
                ctx = (conn, cur, targets if is_agg else mutatable, is_agg)
                if self._try_mutations(ctx, query, orig_rows, attempts):
                    return MutationResult()
                return MutationResult(
                    is_valid=False, error="mutazione non cambia il risultato"
                )

    @staticmethod
    def _base_tables(cur: Any) -> set[str]:
        """Restituisce l'insieme delle tabelle base nello schema corrente."""
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
        )
        return {r[0] for r in cur.fetchall()}

    @staticmethod
    def _filter_mutatable(cur: Any, tables: list[str], query: str) -> list[str]:
        """Filtra le tabelle che hanno almeno una colonna mutabile usata nella query."""
        result = []
        for t in tables:
            used = _get_used_columns(query, t)
            if _has_mutatable_cols(cur, t, used):
                result.append(t)
        return result

    @staticmethod
    def _safe_query(cur: Any, conn: Any, query: str) -> list[tuple] | None:
        """Esegue la query in modo sicuro, restituendo None in caso di errore."""
        try:
            cur.execute(query)
            return cur.fetchall()
        except PgError:
            conn.rollback()
            return None

    @staticmethod
    def _try_mutations(
        ctx: tuple, query: str, orig: list[tuple], attempts: int
    ) -> bool:
        """Tenta mutazioni casuali finche' una produce un risultato diverso."""
        conn, cur, tables, is_agg = ctx
        for _ in range(attempts):
            table = choice(tables)
            try:
                if is_agg:
                    changed = _delete_one_row(conn, cur, table)
                else:
                    changed = _mutate_random_cell(conn, cur, table, query)
                if not changed:
                    conn.rollback()
                    continue
                cur.execute(query)
                new_rows = cur.fetchall()
                conn.rollback()
                if new_rows != orig:
                    return True
            except PgError:
                conn.rollback()
        return False

    @staticmethod
    def _is_scalar_aggregate(query: str) -> bool:
        """Verifica se la query e' un'aggregazione scalare (senza GROUP BY)."""
        try:
            tree = parse_one(query, read="postgres")
            return bool(tree.find(exp.AggFunc)) and tree.args.get("group") is None
        except Exception:
            return False


def _delete_one_row(conn: Any, cur: Any, table: str) -> bool:
    """Elimina una riga casuale da una tabella."""
    stmt = sql.SQL(
        "DELETE FROM {} WHERE ctid IN (SELECT ctid FROM {} ORDER BY random() LIMIT 1)"
    ).format(sql.Identifier(table), sql.Identifier(table))
    try:
        cur.execute(stmt)
        return cur.rowcount > 0
    except ForeignKeyViolation:
        conn.rollback()
        return False


def _mutate_random_cell(conn: Any, cur: Any, table: str, query: str) -> bool:
    """Modifica un valore casuale in una riga della tabella."""
    excluded = _excluded_cols(cur, table)
    cur.execute(
        "SELECT column_name, data_type, character_maximum_length "
        "FROM information_schema.columns "
        "WHERE table_name = %s AND table_schema = current_schema()",
        (table,),
    )
    cols_info = cur.fetchall()
    used = _get_used_columns(query, table)
    candidates = [c for c in cols_info if c[0] not in excluded and c[1] in _MUTATABLE_TYPES]
    if used:
        candidates = [c for c in candidates if c[0] in used]
    if not candidates:
        return False
    shuffle(candidates)
    return _apply_mutation(conn, cur, table, candidates)


def _apply_mutation(conn: Any, cur: Any, table: str, candidates: list) -> bool:
    """Applica una mutazione a una colonna casuale di una riga."""
    for col_name, col_type, max_len in candidates:
        stmt = sql.SQL("SELECT ctid, {} FROM {} ORDER BY random() LIMIT 1").format(
            sql.Identifier(col_name), sql.Identifier(table)
        )
        cur.execute(stmt)
        row = cur.fetchone()
        if row is None:
            continue
        new_val = _gen_mutation(row[1], col_type, max_len)
        if new_val is None:
            continue
        try:
            update = sql.SQL("UPDATE {} SET {} = %s WHERE ctid = %s").format(
                sql.Identifier(table), sql.Identifier(col_name)
            )
            cur.execute(update, (new_val, row[0]))
            return True
        except PgError:
            conn.rollback()
    return False


def _excluded_cols(cur: Any, table: str) -> set[str]:
    """Restituisce le colonne con vincoli PK, FK o UNIQUE da escludere dalla mutazione."""
    cur.execute(
        "SELECT kcu.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
        "WHERE tc.table_name = %s AND tc.table_schema = current_schema() "
        "AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')",
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def _get_used_columns(query: str, table_name: str) -> set[str]:
    """Estrae i nomi colonna usati per una tabella nella query SQL."""
    try:
        tree = parse_one(query, read="postgres")
        used: set[str] = set()
        aliases = {table_name.lower()}
        for t in tree.find_all(exp.Table):
            if t.name.lower() == table_name.lower() and t.alias:
                aliases.add(t.alias.lower())
        for c in tree.find_all(exp.Column):
            if c.table and c.table.lower() in aliases:
                used.add(c.name.lower())
            elif not c.table:
                used.add(c.name.lower())
        return used
    except Exception:
        return set()


def _has_mutatable_cols(cur: Any, table: str, used: set[str]) -> bool:
    """Verifica se la tabella ha colonne mutabili (non PK/FK/UNIQUE, tipo supportato)."""
    excluded = _excluded_cols(cur, table)
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = %s AND table_schema = current_schema()",
        (table,),
    )
    candidates = [
        (r[0], r[1])
        for r in cur.fetchall()
        if r[0] not in excluded and r[1] in _MUTATABLE_TYPES
    ]
    if used:
        candidates = [(n, d) for n, d in candidates if n in used]
    return bool(candidates)


def _gen_mutation(old_val: Any, col_type: str, max_len: int | None) -> Any:
    """Genera un valore mutato per un dato tipo di colonna."""
    if "int" in col_type or "numeric" in col_type or "decimal" in col_type:
        return (old_val or 0) + 1
    if "real" in col_type or "double" in col_type:
        return (old_val or 0) + 1.0
    if "char" in col_type or "text" in col_type:
        base = "m_" + (str(old_val) if old_val is not None else "")
        if max_len and len(base) > max_len:
            base = base[:max_len]
        return base
    if col_type == "boolean":
        return not bool(old_val)
    if "date" in col_type or "timestamp" in col_type:
        if old_val is None:
            return date.today()
        return old_val + timedelta(days=1)
    return None
