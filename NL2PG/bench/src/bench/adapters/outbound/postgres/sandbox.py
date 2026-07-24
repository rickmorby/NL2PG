"""Adattatore outbound per l'amministrazione sandbox ed esecuzione AST tramite sqlglot.

:author: Riccardo Morabito
"""

from contextlib import contextmanager
from logging import getLogger
from random import choices
from re import compile as re_compile
from string import ascii_lowercase, digits
from typing import Any, Generator
from sqlglot import parse as parse_sql, exp
from bench.adapters.outbound.postgres.client import PostgresClientAdapter
from bench.domain.exceptions import DatabaseClientError
from bench.domain.ports.outbound.database import SandboxPort

_log = getLogger("bench.adapters.postgres")


class PostgresSandboxAdapter(SandboxPort):
    """Adattatore per la gestione di schemi temporanei sandbox ed esecuzione AST."""

    def __init__(self, client: PostgresClientAdapter):
        """Inizializza l'adattatore memorizzando l'istanza del client PostgreSQL."""
        self._client = client
        self._schema_regex = re_compile(r"^task_[a-z0-9]{12}$")

    def get_client(self) -> PostgresClientAdapter:
        """Restituisce il client di trasporto PostgreSQL."""
        return self._client

    def create_fresh_schema(self) -> str:
        """Crea uno schema temporaneo univoco ed isolato per un task del benchmark."""
        with self._client.get_sandbox_connection() as conn:
            for _ in range(5):
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
        self._validate_schema_name(schema)
        statements = self._validate_and_split_sql(
            ddl,
            allowed_types=(exp.Create, exp.Alter, exp.Comment, exp.Drop),
        )
        with self._client.get_sandbox_connection(schema) as conn:
            with conn.transaction():
                for stmt in statements:
                    self._client.execute_prepared(conn, stmt)

    def execute_inserts(self, schema: str, inserts: str) -> None:
        """Valida l'AST degli INSERT tramite sqlglot ed inserisce i dati nello schema."""
        self._validate_schema_name(schema)
        statements = self._validate_and_split_sql(
            inserts,
            allowed_types=(exp.Insert, exp.Tuple),
        )
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

    @contextmanager
    def task_scope(self, schema: str | None = None) -> Generator[str, None, None]:
        """Context manager che garantisce la distruzione dello schema anche in caso di eccezione."""
        target_schema = schema or self.create_fresh_schema()
        try:
            yield target_schema
        finally:
            self.drop_schema(target_schema)

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
        try:
            parsed_expressions = parse_sql(sql_text, read="postgres")
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
