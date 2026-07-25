"""Adattatore outbound per la validazione dello schema del database dei metadati tramite ormguard.

:author: Riccardo Morabito
"""

from logging import getLogger
from ormguard import assert_schema
from bench.adapters.outbound.postgres.database_adapter import PostgresClientAdapter
from bench.adapters.outbound.postgres.entities import BaseEntity
from bench.domain.exceptions import DatabaseClientError
from bench.domain.ports.outbound.schema_validator_port import DatabaseSchemaValidatorPort

_log = getLogger("bench.adapters.postgres")


class PostgresSchemaValidatorAdapter(DatabaseSchemaValidatorPort):
    """Adattatore per la verifica dello schema fisico bench_meta tramite ormguard."""

    def __init__(self, client: PostgresClientAdapter):
        """Inizializza l'adattatore memorizzando l'istanza del client PostgreSQL."""
        self._client = client

    def validate_meta_schema(self) -> None:
        """Verifica lo schema bench_meta con ormguard.assert_schema(strict=True)."""
        engine = self._client.get_meta_engine()
        mismatches = assert_schema(engine, BaseEntity, strict=True)
        if mismatches:
            raise DatabaseClientError(f"Disallineamento dello schema bench_meta: {mismatches}")
        _log.info("Validazione dello schema bench_meta completata con successo (ormguard).")
