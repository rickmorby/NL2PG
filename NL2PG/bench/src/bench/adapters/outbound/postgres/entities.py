"""Entità ORM che modellano le tabelle del database metadati bench_meta.

:author: Riccardo Morabito
"""

from typing import ClassVar
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseEntity(DeclarativeBase):
    """Classe base declarativa per le entità SQLAlchemy del benchmark."""



class RunEntity(BaseEntity):
    """Entità ORM che modella la tabella bench_meta.runs."""

    __tablename__ = "runs"
    __table_args__: ClassVar = {"schema": "bench_meta"}

    id: Mapped[str] = mapped_column(String, primary_key=True)
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    categories_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class TaskEntity(BaseEntity):
    """Entità ORM che modella la tabella bench_meta.tasks."""

    __tablename__ = "tasks"
    __table_args__: ClassVar = (
        Index("idx_tasks_category", "category"),
        Index("idx_tasks_run_id", "run_id"),
        Index("idx_tasks_spec_hash", "spec_hash"),
        {"schema": "bench_meta"},
    )

    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    spec_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    difficulty_label: Mapped[str | None] = mapped_column(String, nullable=True)
    critic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    last_model: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_schema: Mapped[int] = mapped_column(Integer, default=0)
    retry_data: Mapped[int] = mapped_column(Integer, default=0)
    retry_query: Mapped[int] = mapped_column(Integer, default=0)
    retry_story: Mapped[int] = mapped_column(Integer, default=0)
    retry_question: Mapped[int] = mapped_column(Integer, default=0)
    retry_critic: Mapped[int] = mapped_column(Integer, default=0)
    retry_hardening: Mapped[int] = mapped_column(Integer, default=0)
    judge_regens: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_ddl: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_inserts: Mapped[str | None] = mapped_column(Text, nullable=True)
    gold_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    gold_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    story: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

