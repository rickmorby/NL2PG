"""Adattatore outbound per il trasporto database PostgreSQL basato su psycopg_pool.

:author: Riccardo Morabito
"""

from contextlib import contextmanager
from logging import getLogger
from typing import Any, Generator
from psycopg import Connection, errors as pg_errors, rows, sql
from psycopg_pool import ConnectionPool
from bench.domain.exceptions import DatabaseClientError
from bench.domain.ports.outbound.database import DatabasePort

_log = getLogger("bench.adapters.postgres")


class PostgresClientAdapter(DatabasePort):
    """Adattatore concreto per il database PostgreSQL con gestione nativa dei ConnectionPool."""

    def __init__(
        self,
        sandbox_dsn: str = "",
        meta_dsn: str = "",
        config: dict[str, Any] | None = None,
        min_size: int = 1,
        max_size: int = 10,
        statement_timeout_ms: int = 5000,
        lock_timeout_ms: int = 5000,
    ):
        """Inizializza l'adattatore creando i pool per sandbox e meta database."""
        self._config = config or {}
        self._sandbox_dsn = sandbox_dsn or self._config.get("sandbox_dsn", "")
        self._meta_dsn = meta_dsn or self._config.get("meta_dsn", "")
        self._statement_timeout_ms = statement_timeout_ms
        self._lock_timeout_ms = lock_timeout_ms

        options_str = f"-c lock_timeout={self._lock_timeout_ms}ms"

        self._sandbox_pool: ConnectionPool | None = (
            ConnectionPool(
                self._sandbox_dsn,
                min_size=min_size,
                max_size=max_size,
                kwargs={"options": options_str},
                open=False,
            )
            if self._sandbox_dsn
            else None
        )

        self._meta_pool: ConnectionPool | None = (
            ConnectionPool(
                self._meta_dsn,
                min_size=min_size,
                max_size=max_size,
                open=False,
            )
            if self._meta_dsn
            else None
        )

    def get_sandbox_dsn(self) -> str:
        """Restituisce il DSN del database sandbox."""
        return self._sandbox_dsn

    def get_meta_dsn(self) -> str:
        """Restituisce il DSN del database dei metadati."""
        return self._meta_dsn

    def open(self) -> None:
        """Apre esplicitamente i connection pool."""
        if self._sandbox_pool and self._sandbox_pool.closed:
            self._sandbox_pool.open()
        if self._meta_pool and self._meta_pool.closed:
            self._meta_pool.open()

    @contextmanager
    def get_meta_connection(self) -> Generator[Connection, None, None]:
        """Ottiene una connessione dal pool dei metadati."""
        if not self._meta_pool:
            raise DatabaseClientError("Pool del database meta non configurato.")
        if self._meta_pool.closed:
            self._meta_pool.open()
        try:
            with self._meta_pool.connection() as conn:
                conn.autocommit = True
                yield conn
        except pg_errors.Error as e:
            raise DatabaseClientError(f"Errore nella connessione meta: {e}") from e

    @contextmanager
    def get_sandbox_connection(
        self, schema: str = "", autocommit: bool = False
    ) -> Generator[Connection, None, None]:
        """Ottiene una connessione dal pool sandbox impostando eventualmente il search_path."""
        if not self._sandbox_pool:
            raise DatabaseClientError("Pool del database sandbox non configurato.")
        if self._sandbox_pool.closed:
            self._sandbox_pool.open()
        try:
            with self._sandbox_pool.connection() as conn:
                conn.autocommit = autocommit
                if schema:
                    conn.execute(sql.SQL("SET search_path = {}").format(sql.Identifier(schema)))
                yield conn
        except pg_errors.Error as e:
            raise DatabaseClientError(f"Errore nella connessione sandbox: {e}") from e

    def execute_prepared(
        self,
        conn: Connection,
        statement: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> None:
        """Esegue uno statement o comando SQL parametrizzato tramite prepared statement."""
        try:
            with conn.cursor() as cur:
                cur.execute(statement, params)
        except pg_errors.Error as e:
            raise DatabaseClientError(f"Errore durante l'esecuzione dello statement SQL: {e}") from e

    def execute_identifier(self, conn: Connection, template: str, identifier: str) -> None:
        """Esegue un comando DDL inserendo un identificatore dinamico con sql.Identifier."""
        try:
            with conn.cursor() as cur:
                query_obj = sql.SQL(template).format(sql.Identifier(identifier))
                cur.execute(query_obj)
        except pg_errors.Error as e:
            raise DatabaseClientError(f"Errore durante l'esecuzione dell'identificatore SQL: {e}") from e

    def execute_query(
        self,
        conn: Connection,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Esegue una query SELECT parametrizzata impostando statement_timeout e modalità read-only."""
        try:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{self._statement_timeout_ms}ms'")
                cur.execute(query, params)
                if cur.description is None:
                    return [], []
                cols = [d.name for d in cur.description]
                return cols, cur.fetchall()
        except pg_errors.Error as e:
            raise DatabaseClientError(f"Errore durante l'esecuzione della query SELECT: {e}") from e

    def execute_query_dict(
        self,
        conn: Connection,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Esegue una query SELECT e restituisce i risultati sotto forma di dizionari."""
        try:
            conn.read_only = True
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(f"SET statement_timeout = '{self._statement_timeout_ms}ms'")
                cur.execute(query, params)
                return cur.fetchall()
        except pg_errors.Error as e:
            raise DatabaseClientError(f"Errore durante l'esecuzione della query dict: {e}") from e

    def close(self) -> None:
        """Chiude i pool rilasciando le connessioni aperte verso PostgreSQL."""
        if self._sandbox_pool and not self._sandbox_pool.closed:
            self._sandbox_pool.close()
        if self._meta_pool and not self._meta_pool.closed:
            self._meta_pool.close()
        _log.info("Pool PostgreSQL chiusi correttamente.")
