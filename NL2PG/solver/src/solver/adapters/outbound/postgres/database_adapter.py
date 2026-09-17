"""Adattatore outbound per il trasporto database PostgreSQL per il solver.

:author: Riccardo Morabito
"""

from contextlib import contextmanager
from logging import getLogger
from typing import Any, Generator

from psycopg import Connection, errors as pg_errors, sql
from psycopg_pool import ConnectionPool

from solver.adapters.outbound.postgres.loaders import register_json_safe_loaders
from solver.domain.exceptions import SandboxSolverError

_log = getLogger("solver.adapters.postgres")


class PostgresClientAdapter:
    """Adattatore PostgreSQL per il solver basato su ConnectionPool."""

    def __init__(self, sandbox_dsn: str = "", options: dict[str, Any] | None = None) -> None:
        """Inizializza l'adattatore creando il pool per il database sandbox del solver."""
        register_json_safe_loaders()
        opts = options or {}
        min_size = opts.get("min_size", 1)
        max_size = opts.get("max_size", 10)
        self._statement_timeout_ms = opts.get("statement_timeout_ms", 5000)

        options_str = "-c lock_timeout=5000ms"

        default_dsn = "postgresql://solver:solver@127.0.0.1:5433/solver_sandbox"
        self._sandbox_dsn = sandbox_dsn or default_dsn
        self._pool: ConnectionPool = ConnectionPool(
            self._sandbox_dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"options": options_str},
            open=False,
        )

    def open(self) -> None:
        """Apre il connection pool."""
        if self._pool.closed:
            self._pool.open()

    @contextmanager
    def get_sandbox_connection(
        self, schema: str = "", autocommit: bool = False
    ) -> Generator[Connection, None, None]:
        """Ottiene una connessione dal pool impostando eventualmente il search_path."""
        if self._pool.closed:
            self._pool.open()
        try:
            with self._pool.connection() as conn:
                conn.autocommit = autocommit
                if schema:
                    conn.execute(sql.SQL("SET search_path = {}").format(sql.Identifier(schema)))
                yield conn
        except pg_errors.Error as e:
            raise SandboxSolverError(f"Errore nella connessione sandbox: {e}") from e

    def execute_prepared(
        self,
        conn: Connection,
        statement: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> None:
        """Esegue uno statement SQL parametrizzato."""
        try:
            with conn.cursor() as cur:
                cur.execute(statement, params)
        except pg_errors.Error as e:
            raise SandboxSolverError(f"Errore durante l'esecuzione dello statement SQL: {e}") from e

    def execute_identifier(self, conn: Connection, template: str, identifier: str) -> None:
        """Esegue un comando DDL inserendo un identificatore dinamico sicuro."""
        try:
            with conn.cursor() as cur:
                query_obj = sql.SQL(template).format(sql.Identifier(identifier))
                cur.execute(query_obj)
        except pg_errors.Error as e:
            msg = f"Errore durante l'esecuzione dell'identificatore SQL: {e}"
            raise SandboxSolverError(msg) from e

    def execute_query(
        self,
        conn: Connection,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Esegue una query SELECT parametrizzata."""
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{self._statement_timeout_ms}ms'")
                cur.execute(query, params)
                if cur.description is None:
                    return [], []
                cols = [d.name for d in cur.description]
                return cols, cur.fetchall()
        except pg_errors.Error as e:
            raise SandboxSolverError(f"Errore durante l'esecuzione della query SELECT: {e}") from e

    def close(self) -> None:
        """Chiude il connection pool."""
        if not self._pool.closed:
            self._pool.close()
