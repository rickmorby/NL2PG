"""Componente ausiliario per il data mutation testing su PostgreSQL Sandbox.

:author: Riccardo Morabito
"""

from datetime import date, timedelta
from random import choice, shuffle
from typing import Any

from psycopg import Connection, sql
from psycopg.errors import Error as PgError, ForeignKeyViolation
from sqlglot import exp, parse_one

_MUTATABLE_TYPES = frozenset(
    {
        "integer",
        "bigint",
        "smallint",
        "numeric",
        "decimal",
        "real",
        "double precision",
        "text",
        "character varying",
        "char",
        "character",
        "boolean",
        "date",
        "timestamp without time zone",
        "timestamp with time zone",
        "timestamp",
    }
)


class PostgresDataMutator:
    """Motore di data mutation testing su database e schemi temporanei PostgreSQL."""

    def test_mutation(
        self, conn: Connection, query: str, tables: list[str], attempts: int = 3
    ) -> tuple[bool, str]:
        """Testa se la query e' sensibile a mutazioni dei dati nello schema corrente."""
        if not tables:
            return True, ""
        with conn.cursor() as cur:
            base_tables = self._base_tables(cur)
            targets = [t for t in tables if t in base_tables]
            if not targets:
                return True, ""
            is_agg = self._is_scalar_aggregate(query)
            mutatable = self._filter_mutatable(cur, targets, query)
            if not is_agg and not mutatable:
                return False, "nessuna colonna mutabile usata e query non aggregata"
            orig_rows = self._safe_query(cur, conn, query)
            if orig_rows is None:
                return False, "esecuzione query fallita durante test mutazione"
            ctx = (conn, cur, targets if is_agg else mutatable, is_agg)
            if self._try_mutations(ctx, query, orig_rows, attempts):
                return True, ""
            return False, "mutazione non cambia il risultato"

    def _base_tables(self, cur: Any) -> set[str]:
        """Restituisce l'insieme delle tabelle base nello schema corrente."""
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
        )
        return {r[0] for r in cur.fetchall()}

    def _filter_mutatable(self, cur: Any, tables: list[str], query: str) -> list[str]:
        """Filtra le tabelle che hanno almeno una colonna mutabile usata nella query."""
        result = []
        for t in tables:
            used = self._get_used_columns(query, t)
            if self._has_mutatable_cols(cur, t, used):
                result.append(t)
        return result

    def _safe_query(self, cur: Any, conn: Connection, query: str) -> list[tuple] | None:
        """Esegue la query in modo sicuro, restituendo None in caso di errore."""
        try:
            cur.execute(query)
            return cur.fetchall()
        except PgError:
            conn.rollback()
            return None

    def _try_mutations(self, ctx: tuple, query: str, orig: list[tuple], attempts: int) -> bool:
        """Tenta mutazioni casuali (UPDATE e fallback DELETE) per alterare il risultato."""
        conn, cur, tables, is_agg = ctx
        for _ in range(attempts):
            table = choice(tables)
            methods = (
                [self._delete_one_row]
                if is_agg
                else [self._mutate_random_cell, self._delete_one_row]
            )
            for method in methods:
                try:
                    changed = method(conn, cur, table)
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

    def _is_scalar_aggregate(self, query: str) -> bool:
        """Verifica se la query e' un'aggregazione scalare (senza GROUP BY)."""
        try:
            tree = parse_one(query, read="postgres")
            return bool(tree.find(exp.AggFunc)) and tree.args.get("group") is None
        except Exception:
            return False

    def _delete_one_row(self, conn: Connection, cur: Any, table: str) -> bool:
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

    def _mutate_random_cell(self, conn: Connection, cur: Any, table: str, query: str) -> bool:
        """Modifica un valore casuale in una riga della tabella."""
        candidates = self._get_mutatable_candidates(cur, table, query)
        if not candidates:
            return False
        shuffle(candidates)
        return self._apply_mutation(conn, cur, table, candidates)

    def _apply_mutation(self, conn: Connection, cur: Any, table: str, candidates: list) -> bool:
        """Applica una mutazione a una colonna casuale di una riga."""
        for col_name, col_type, max_len in candidates:
            stmt = sql.SQL("SELECT ctid, {} FROM {} ORDER BY random() LIMIT 1").format(
                sql.Identifier(col_name), sql.Identifier(table)
            )
            cur.execute(stmt)
            row = cur.fetchone()
            if row is None:
                continue
            new_val = self._gen_mutation(row[1], col_type, max_len)
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

    def _excluded_cols(self, cur: Any, table: str) -> set[str]:
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

    def _get_used_columns(self, query: str, table_name: str) -> set[str]:
        """Estrae i nomi colonna usati per una tabella nella query SQL."""
        try:
            tree = parse_one(query, read="postgres")
            used: set[str] = set()
            aliases = {table_name.lower()}
            for t in tree.find_all(exp.Table):
                if t.name.lower() == table_name.lower() and t.alias:
                    aliases.add(t.alias.lower())
            for c in tree.find_all(exp.Column):
                if (c.table and c.table.lower() in aliases) or not c.table:
                    used.add(c.name.lower())
            return used
        except Exception:
            return set()

    def _has_mutatable_cols(self, cur: Any, table: str, _used: set[str]) -> bool:
        """Verifica se la tabella ha colonne mutabili (non PK/FK/UNIQUE, tipo supportato)."""
        return bool(self._get_mutatable_candidates(cur, table, ""))

    def _get_mutatable_candidates(
        self, cur: Any, table: str, query: str = ""
    ) -> list[tuple[str, str, int | None]]:
        """Estrae le colonne mutabili valide da information_schema.columns."""
        excluded = self._excluded_cols(cur, table)
        cur.execute(
            "SELECT column_name, data_type, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_name = %s AND table_schema = current_schema()",
            (table,),
        )
        cols_info = cur.fetchall()
        used = self._get_used_columns(query, table) if query else set()
        candidates = [c for c in cols_info if c[0] not in excluded and c[1] in _MUTATABLE_TYPES]
        if used:
            candidates = [c for c in candidates if c[0] in used]
        return candidates

    def _gen_mutation(self, old_val: Any, col_type: str, max_len: int | None) -> Any:
        """Genera un valore mutato per un dato tipo di colonna."""
        match col_type:
            case t if any(k in t for k in ("int", "numeric", "decimal")):
                return (old_val or 0) + 1
            case t if any(k in t for k in ("real", "double")):
                return (old_val or 0) + 1.0
            case t if any(k in t for k in ("char", "text")):
                base = "m_" + (str(old_val) if old_val is not None else "")
                return base[:max_len] if max_len and len(base) > max_len else base
            case "boolean":
                return not bool(old_val)
            case t if any(k in t for k in ("date", "timestamp")):
                return date.today() if old_val is None else old_val + timedelta(days=1)
            case _:
                return None
