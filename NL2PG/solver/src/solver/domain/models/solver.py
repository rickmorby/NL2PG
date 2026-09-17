"""DTO per i risultati di esecuzione e la serializzazione delle run del solver.

:author: Riccardo Morabito
"""

from enum import Enum

from pydantic import Field

from solver.domain.models.base import AbstractDTO
from solver.domain.models.error import ErrorType
from solver.domain.models.trace import ToolTraceDTO


class RecipeType(str, Enum):
    """Ricette sperimentali formali per la risoluzione del benchmark."""

    TEXT_TO_SCHEMA_RAG_SANDBOX = "text_to_schema_rag_sandbox"
    TEXT_TO_SQL_RAG_SANDBOX = "text_to_sql_rag_sandbox"
    TEXT_TO_SQL_ZERO_SHOT = "text_to_sql_zero_shot"
    TEXT_TO_DATALOG_RAG_CLINGO = "text_to_datalog_rag_clingo"
    SQL_TO_DATALOG_TRANSPILED = "sql_to_datalog_transpiled"


class SchemaSource(str, Enum):
    """Sorgente dello schema usato per la risoluzione della query."""

    GOLD = "gold"
    GENERATED = "generated"


class RecipeResultDTO(AbstractDTO):
    """Risultato dell'esecuzione di una singola ricetta su un task."""

    recipe: str = Field(default="")
    schema_source: str = Field(default=SchemaSource.GOLD.value)
    generated_code: str = Field(default="")
    intermediate_sql: str | None = Field(default=None)
    translation_mode: str = Field(default="")
    datalog_scale: int = Field(default=0)
    match_gold: bool = Field(default=False)
    error_type: ErrorType | None = Field(default=None)
    error_message: str | None = Field(default=None)
    trace: ToolTraceDTO = Field(default_factory=ToolTraceDTO)
    duration_seconds: float = Field(default=0.0)
    execution_time_ms: float = Field(default=0.0)
    schema_f1: float | None = Field(default=None)
    schema_accuracy: float | None = Field(default=None)
    table_f1: float | None = Field(default=None)
    column_f1: float | None = Field(default=None)
    pk_f1: float | None = Field(default=None)
    fk_f1: float | None = Field(default=None)


class TaskSolverResultDTO(AbstractDTO):
    """Risultato completo della risoluzione per un singolo task del benchmark."""

    task_id: str = Field(default="")
    category: str = Field(default="")
    domain: str = Field(default="")
    n_tables: int = Field(default=1)
    sql_features: list[str] = Field(default_factory=list)
    twists: list[str] = Field(default_factory=list)
    difficulty_label: str = Field(default="hard")
    story: str = Field(default="")
    question: str = Field(default="")

    schema_phase: RecipeResultDTO | None = Field(default=None)
    query_phase: dict[str, RecipeResultDTO] = Field(default_factory=dict)


class SolverRunSummaryDTO(AbstractDTO):
    """Sintesi statistica globale di una run del solver."""

    total_tasks: int = Field(default=0)
    tasks_evaluated: int = Field(default=0)
    pass_rate_global: float = Field(default=0.0)
    pass_rate_sql_rag_sandbox_gold: float = Field(default=0.0)
    pass_rate_sql_zero_shot_gold: float = Field(default=0.0)
    pass_rate_datalog_rag_clingo_gold: float = Field(default=0.0)
    pass_rate_sql_to_datalog_transpiled_gold: float = Field(default=0.0)
    pass_rate_sql_rag_sandbox_generated: float = Field(default=0.0)
    pass_rate_datalog_rag_clingo_generated: float = Field(default=0.0)
    schema_accuracy: float = Field(default=0.0)
    schema_f1_mean: float = Field(default=0.0)
    schema_gap: float = Field(default=0.0)
    one_shot_rate: float = Field(default=0.0)
    tool_usage_rate: float = Field(default=0.0)
    duration_seconds: float = Field(default=0.0)


class SolverRunDTO(AbstractDTO):
    """Oggetto radice serializzato in JSON per l'intera run del solver."""

    version: int = Field(default=1)
    run_id: str = Field(default="")
    generated_at: str = Field(default="")
    benchmark_source: str = Field(default="")
    model_name: str = Field(default="")
    summary: SolverRunSummaryDTO = Field(default_factory=SolverRunSummaryDTO)
    tasks: list[TaskSolverResultDTO] = Field(default_factory=list)
