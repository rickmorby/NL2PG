"""Adattatore outbound per la persistenza dei metadati tramite SQLAlchemy 2.0.

:author: Riccardo Morabito
"""

from uuid import uuid4
from psycopg import errors as pg_errors
from sqlalchemy import func, select
from bench.adapters.outbound.postgres.database_adapter import PostgresClientAdapter
from bench.adapters.outbound.postgres.entities import RunEntity, TaskEntity
from bench.adapters.outbound.postgres.mappers import TaskStateMapper
from bench.domain.exceptions import DatabaseClientError
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.repository_port import MetaRepositoryPort


class MetaRepositoryAdapter(MetaRepositoryPort):
    """Adattatore per la persistenza dei task su bench_meta basato su SQLAlchemy ORM."""

    def __init__(self, client: PostgresClientAdapter):
        """Inizializza l'adattatore memorizzando l'istanza del client PostgreSQL."""
        self._client = client

    def new_run(self, config_hash: str, categories_hash: str) -> str:
        """Registra una nuova esecuzione e restituisce l'identificativo univoco run_id."""
        run_id = f"run-{uuid4().hex[:12]}"
        run_entity = RunEntity(
            id=run_id,
            config_hash=config_hash,
            categories_hash=categories_hash,
        )
        try:
            with self._client.get_meta_session() as session:
                session.add(run_entity)
                session.commit()
            return run_id
        except DatabaseClientError:
            raise
        except (pg_errors.Error, Exception) as e:
            msg = f"Errore durante la registrazione della nuova run: {e}"
            raise DatabaseClientError(msg) from e

    def is_spec_duplicated(self, category: str, spec_hash: str) -> bool:
        """Verifica se una specifica è presente per la categoria in stato accepted/pending."""
        if not spec_hash:
            return False
        try:
            with self._client.get_meta_session() as session:
                stmt = (
                    select(TaskEntity)
                    .where(TaskEntity.category == category)
                    .where(TaskEntity.spec_hash == spec_hash)
                    .where(TaskEntity.verdict.in_(["accepted", "pending"]))
                    .limit(1)
                )
                result = session.scalars(stmt).first()
                return result is not None
        except DatabaseClientError:
            raise
        except (pg_errors.Error, Exception) as e:
            msg = f"Errore durante la verifica della deduplicazione: {e}"
            raise DatabaseClientError(msg) from e

    def save_task(self, run_id: str, state: TaskStateDTO) -> None:
        """Esegue l'upsert dello stato di un task mediante SQLAlchemy ORM session.merge."""
        task_entity = TaskStateMapper.dto_to_entity(run_id, state)
        try:
            with self._client.get_meta_session() as session:
                session.merge(task_entity)
                session.commit()
        except DatabaseClientError:
            raise
        except (pg_errors.Error, Exception) as e:
            msg = f"Errore durante il salvataggio del task {state.task_id}: {e}"
            raise DatabaseClientError(msg) from e

    def get_run_verdict_counts(self, run_id: str) -> dict[str, int]:
        """Calcola i conteggi aggregati dei verdetti registrati per una determinata run dal DB."""
        try:
            with self._client.get_meta_session() as session:
                stmt = (
                    select(TaskEntity.verdict, func.count(TaskEntity.task_id))
                    .where(TaskEntity.run_id == run_id)
                    .group_by(TaskEntity.verdict)
                )
                results = session.execute(stmt).all()
                return {verdict: count for verdict, count in results}
        except DatabaseClientError:
            raise
        except (pg_errors.Error, Exception) as e:
            msg = f"Errore durante il recupero delle statistiche per la run '{run_id}': {e}"
            raise DatabaseClientError(msg) from e
