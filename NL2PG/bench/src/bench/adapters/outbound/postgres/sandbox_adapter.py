"""Adattatore outbound per l'amministrazione sandbox ed esecuzione AST tramite sqlglot.

:author: Riccardo Morabito
"""

from contextlib import contextmanager
from datetime import date, timedelta
from logging import getLogger
from random import choice, choices, shuffle
from re import compile as re_compile
from string import ascii_lowercase, digits
from typing import Any, Generator

from psycopg import sql
from psycopg.errors import Error as PgError, ForeignKeyViolation
from sqlglot import exp, parse as parse_sql, parse_one

from bench.adapters.outbound.postgres.database_adapter import PostgresClientAdapter
from bench.domain.exceptions import DatabaseClientError
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.sql_repair import PostgresSQLRepair

_log = getLogger("bench.adapters.postgres")

_MUTATABLE_TYPES = frozenset({
    "integer", "bigint", "smallint",
    "numeric", "decimal", "real", "double precision",
    "text", "character varying", "char", "character",
    "boolean", "date", "timestamp without time zone",
    "timestamp with time zone", "timestamp",
})
_SCHEMA_MAX_RETRIES = 5


class PostgresSandboxAdapter(SandboxPort):
    """Adattatore per la gestione di schemi temporanei sandbox ed esecuzione AST."""

    def __init__(self, client: PostgresClientAdapter):
        """Inizializza l'adattatore memorizzando l'istanza del client PostgreSQL."""
        self._client = client
        self._schema_regex = re_compile(r"^task_[a-z0-9]{12}$")
        self._repair = PostgresSQLRepair()

    def get_client(self) -> PostgresClientAdapter:
        """Restituisce il client di trasporto PostgreSQL."""
        return self._client

    def create_fresh_schema(self) -> str:
        """Crea uno schema temporaneo univoco ed isolato per un task del benchmark."""
        with self._client.get_sandbox_connection() as conn:
            for _ in range(_SCHEMA_MAX_RETRIES):
                candidate = f"task_{self._generate_random_id()}"
                try:
                    self._client.execute_identifier(conn, "CREATE SCHEMA {}", candidate)
                    conn.commit()
                    return candidate
                except DatabaseClientError:
                    conn.rollback()
        raise DatabaseClientError("Impossibile generare uno schema effimero univoco.")

    def execute_ddl(self, schema: str, ddl: str) -> None:
        """Valida l'AST del DDL tramite sqlglot ed esegue la creazione tabelle nello schema."""
        self._execute_statements(
            schema, ddl, allowed_types=(exp.Create, exp.Alter, exp.Comment, exp.Drop)
        )

    def execute_inserts(self, schema: str, inserts: str) -> None:
        """Valida l'AST degli INSERT tramite sqlglot ed inserisce i dati nello schema."""
        self._execute_statements(
            schema, inserts, allowed_types=(exp.Insert, exp.Tuple)
        )

    def _execute_statements(
        self, schema: str, sql_text: str, allowed_types: tuple[type, ...]
    ) -> None:
        """Esegue atomicamente un blocco di istruzioni SQL ammesse in transazione isolata."""
        self._validate_schema_name(schema)
        statements = self._validate_and_split_sql(sql_text, allowed_types=allowed_types)
        with self._client.get_sandbox_connection(schema) as conn:
            with conn.transaction():
                for stmt in statements:
                    self._client.execute_prepared(conn, stmt)

    def run_query(self, schema: str, query: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Valida che la query sia una SELECT read-only ed esegue la lettura nello schema."""
        self._validate_schema_name(schema)
        statements = self._validate_and_split_sql(
            query,
            allowed_types=(exp.Select, exp.Union),
        )
        if not statements:
            return [], []
        with self._client.get_sandbox_connection(schema, autocommit=True) as conn:
            return self._client.execute_query(conn, statements[0])

    def drop_schema(self, schema: str) -> None:
        """Elimina uno schema temporaneo e le relative tabelle liberando le risorse."""
        self._validate_schema_name(schema)
        try:
            with self._client.get_sandbox_connection(autocommit=True) as conn:
                self._client.execute_identifier(conn, "DROP SCHEMA IF EXISTS {} CASCADE", schema)
        except DatabaseClientError as e:
            _log.warning("nodo=cleanup schema=%s errore=%s (ignorato)", schema, str(e)[:100])

    def cleanup_orphan_schemas(self) -> list[str]:
        """Elimina tutti gli schemi temporanei orfani (task_*) nel database sandbox."""
        removed_schemas: list[str] = []
        with self._client.get_sandbox_connection(autocommit=True) as conn:
            query = (
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'task_%'"
            )
            _, rows = self._client.execute_query(conn, query)
            target_schemas = [r[0] for r in rows if self._schema_regex.match(r[0])]
            if not target_schemas:
                return []
            identifiers = sql.SQL(", ").join(sql.Identifier(s) for s in target_schemas)
            drop_stmt = sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(identifiers)
            with conn.cursor() as cur:
                cur.execute(drop_stmt)
            removed_schemas.extend(target_schemas)
        return removed_schemas

    def test_data_mutation(
        self, schema: str, query: str, tables: list[str], attempts: int = 3
    ) -> tuple[bool, str]:
        """Testa se la query e' sensibile a mutazioni dei dati nel sandbox."""
        if not tables:
            return True, ""
        self._validate_schema_name(schema)
        with self._client.get_sandbox_connection(schema) as conn:
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

    @contextmanager
    def task_scope(self, schema: str | None = None) -> Generator[str, None, None]:
        """Context manager che garantisce la distruzione dello schema anche in caso di eccezione."""
        target_schema = schema or self.create_fresh_schema()
        try:
            yield target_schema
        finally:
            self.drop_schema(target_schema)


    @staticmethod
    def _base_tables(cur: Any) -> set[str]:
        """Restituisce l'insieme delle tabelle base nello schema corrente."""
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
        )
        return {r[0] for r in cur.fetchall()}

    @classmethod
    def _filter_mutatable(cls, cur: Any, tables: list[str], query: str) -> list[str]:
        """Filtra le tabelle che hanno almeno una colonna mutabile usata nella query."""
        result = []
        for t in tables:
            used = cls._get_used_columns(query, t)
            if cls._has_mutatable_cols(cur, t, used):
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

    @classmethod
    def _try_mutations(
        cls, ctx: tuple, query: str, orig: list[tuple], attempts: int
    ) -> bool:
        """Tenta mutazioni casuali finche' una produce un risultato diverso."""
        conn, cur, tables, is_agg = ctx
        for _ in range(attempts):
            table = choice(tables)
            try:
                if is_agg:
                    changed = cls._delete_one_row(conn, cur, table)
                else:
                    changed = cls._mutate_random_cell(conn, cur, table, query)
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

    def _validate_schema_name(self, schema: str) -> None:
        """Valida la sintassi e la sicurezza del nome dello schema temporaneo."""
        if not self._schema_regex.match(schema):
            raise DatabaseClientError(f"Nome dello schema non valido: {schema!r}.")

    def _generate_random_id(self) -> str:
        """Genera una stringa causale di 12 caratteri alfanumerici minuscoli."""
        return "".join(choices(ascii_lowercase + digits, k=12))

    def _validate_and_split_sql(
        self,
        sql_text: str,
        allowed_types: tuple[type, ...],
    ) -> list[str]:
        """Analizza l'AST del testo SQL con sqlglot filtrando le istruzioni non ammesse."""
        repaired_sql = self._repair.repair(sql_text)
        try:
            parsed_expressions = parse_sql(repaired_sql, read="postgres")
        except Exception as e:
            raise DatabaseClientError(f"Errore durante il parsing del codice SQL: {e}") from e

        valid_statements: list[str] = []
        for parsed in parsed_expressions:
            if parsed is None:
                continue
            if not isinstance(parsed, allowed_types):
                raise DatabaseClientError(
                    f"Tipo di istruzione SQL non ammesso: {type(parsed).__name__}."
                )
            stmt_sql = parsed.sql(dialect="postgres")
            if stmt_sql:
                valid_statements.append(stmt_sql)
        return valid_statements

    @staticmethod
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

    @classmethod
    def _mutate_random_cell(cls, conn: Any, cur: Any, table: str, query: str) -> bool:
        """Modifica un valore casuale in una riga della tabella."""
        excluded = cls._excluded_cols(cur, table)
        cur.execute(
            "SELECT column_name, data_type, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_name = %s AND table_schema = current_schema()",
            (table,),
        )
        cols_info = cur.fetchall()
        used = cls._get_used_columns(query, table)
        candidates = [c for c in cols_info if c[0] not in excluded and c[1] in _MUTATABLE_TYPES]
        if used:
            candidates = [c for c in candidates if c[0] in used]
        if not candidates:
            return False
        shuffle(candidates)
        return cls._apply_mutation(conn, cur, table, candidates)

    @classmethod
    def _apply_mutation(cls, conn: Any, cur: Any, table: str, candidates: list) -> bool:
        """Applica una mutazione a una colonna casuale di una riga."""
        for col_name, col_type, max_len in candidates:
            stmt = sql.SQL("SELECT ctid, {} FROM {} ORDER BY random() LIMIT 1").format(
                sql.Identifier(col_name), sql.Identifier(table)
            )
            cur.execute(stmt)
            row = cur.fetchone()
            if row is None:
                continue
            new_val = cls._gen_mutation(row[1], col_type, max_len)
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

    @staticmethod
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

    @staticmethod
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

    @classmethod
    def _has_mutatable_cols(cls, cur: Any, table: str, used: set[str]) -> bool:
        """Verifica se la tabella ha colonne mutabili (non PK/FK/UNIQUE, tipo supportato)."""
        excluded = cls._excluded_cols(cur, table)
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

    @staticmethod
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
