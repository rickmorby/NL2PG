"""Adattatore outbound per il trasporto database PostgreSQL con psycopg_pool e SQLAlchemy.

:author: Riccardo Morabito
"""

from contextlib import contextmanager
from logging import getLogger
from threading import Lock
from typing import Any, Generator

from psycopg import Connection, errors as pg_errors, sql
from psycopg_pool import ConnectionPool
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from bench.adapters.outbound.postgres.loaders import JsonSafeLoadersRegistry
from bench.domain.exceptions import (
    ConfigurationMissingFieldError,
    DatabaseClientError,
    handle_exception,
)
from bench.domain.ports.outbound.database_port import DatabasePort

_log = getLogger("bench.adapters.postgres")


class PostgresClientAdapter(DatabasePort):
    """Adattatore PostgreSQL con gestione di ConnectionPool e Sessioni ORM."""

    def __init__(
        self,
        sandbox_dsn: str = "",
        meta_dsn: str = "",
        config: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ):
        """Inizializza l'adattatore creando i pool ed il sessionmaker dei metadati."""
        JsonSafeLoadersRegistry.register()
        self._config = config or {}
        opts = options or {}
        min_size = opts.get("min_size", 1)
        max_size = opts.get("max_size", 10)
        statement_timeout_ms = opts.get("statement_timeout_ms", 5000)
        lock_timeout_ms = opts.get("lock_timeout_ms", 5000)

        default_sandbox = "postgresql://bench:bench@127.0.0.1:5432/bench_sandbox"
        default_meta = "postgresql://bench:bench@127.0.0.1:5432/bench_meta"

        self._sandbox_dsn = self._resolve_dsn(
            sandbox_dsn, ("sandbox_dsn", "db_dsn"), default_sandbox, "sandbox"
        )
        self._meta_dsn = self._resolve_dsn(meta_dsn, ("meta_dsn",), default_meta, "meta")
        self._statement_timeout_ms = statement_timeout_ms
        self._lock_timeout_ms = lock_timeout_ms
        self._engine_lock = Lock()

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

        self._meta_engine: Engine | None = None
        self._meta_sessionmaker: sessionmaker[Session] | None = None

    def _resolve_dsn(
        self, provided: str, keys: tuple[str, ...], default_dsn: str, db_type: str
    ) -> str:
        """Risolve la stringa DSN dalla configurazione o applica il valore predefinito."""
        resolved = provided
        if not resolved:
            for k in keys:
                resolved = self._config.get(k, "")
                if resolved:
                    break
        if not resolved:
            msg = (
                f"La DSN per il database {db_type} non è stata fornita nella configurazione. "
                f"Viene utilizzato il valore di fallback '{default_dsn}'."
            )
            try:
                raise ConfigurationMissingFieldError(msg, payload={"default": default_dsn})
            except ConfigurationMissingFieldError as e:
                handle_exception(e)
            resolved = default_dsn
        return resolved

    def get_meta_engine(self) -> Engine:
        """Restituisce l'Engine SQLAlchemy dei metadati con thread locking a doppi controlli."""
        if not self._meta_engine:
            with self._engine_lock:
                if not self._meta_engine:
                    if not self._meta_dsn:
                        msg = "DSN del database meta non configurato per l'Engine."
                        raise DatabaseClientError(msg)
                    url = make_url(self._meta_dsn).set(drivername="postgresql+psycopg")
                    self._meta_engine = create_engine(url)
                    self._meta_sessionmaker = sessionmaker(bind=self._meta_engine)
        return self._meta_engine

    @contextmanager
    def get_meta_session(self) -> Generator[Session, None, None]:
        """Context manager per l'acquisizione ed il rilascio di una Sessione SQLAlchemy ORM."""
        if not self._meta_sessionmaker:
            self.get_meta_engine()
        assert self._meta_sessionmaker is not None
        session = self._meta_sessionmaker()
        try:
            yield session
        except (SQLAlchemyError, pg_errors.Error, OSError, ValueError) as e:
            session.rollback()
            raise DatabaseClientError(f"Errore durante l'esecuzione della sessione ORM: {e}") from e
        finally:
            session.close()

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
            msg = f"Errore durante l'esecuzione dello statement SQL: {e}"
            raise DatabaseClientError(msg) from e

    def execute_identifier(self, conn: Connection, template: str, identifier: str) -> None:
        """Esegue un comando DDL inserendo un identificatore dinamico con sql.Identifier."""
        try:
            with conn.cursor() as cur:
                query_obj = sql.SQL(template).format(sql.Identifier(identifier))
                cur.execute(query_obj)
        except pg_errors.Error as e:
            msg = f"Errore durante l'esecuzione dell'identificatore SQL: {e}"
            raise DatabaseClientError(msg) from e

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
            raise DatabaseClientError(f"Errore durante l'esecuzione della query SELECT: {e}") from e

    def close(self) -> None:
        """Chiude i pool ed inattiva l'Engine SQLAlchemy del client."""
        if self._sandbox_pool and not self._sandbox_pool.closed:
            self._sandbox_pool.close()
        if self._meta_pool and not self._meta_pool.closed:
            self._meta_pool.close()
        if self._meta_engine:
            self._meta_engine.dispose()
        _log.info("Client PostgreSQL e risorse ORM chiuse correttamente.")
