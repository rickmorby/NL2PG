"""Servizio di orchestrazione delle run di risoluzione del benchmark.

:author: Riccardo Morabito
"""

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import suppress
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

from orjson import loads as orjson_loads
from psycopg.errors import Error as PgError
from pydantic import ValidationError
from sqlglot import exp, parse as sqlglot_parse
from sqlglot.errors import ParseError, TokenError
from tqdm import tqdm

from solver.domain.exceptions import SandboxSolverError, SolverException

from solver.application.agents.solver_agent import SolverAgent
from solver.domain.exceptions import BenchmarkFormatError
from solver.domain.models.error import ErrorType
from solver.domain.models.solver import (
    RecipeResultDTO,
    RecipeType,
    SchemaSource,
    SolverRunDTO,
    SolverRunSummaryDTO,
    TaskSolverResultDTO,
)
from solver.domain.models.state import SolverTaskStateDTO
from solver.domain.ports.inbound.analytics_port import SolverAnalyticsPort
from solver.domain.ports.inbound.solver_runner_port import SolverRunnerPort
from solver.domain.ports.outbound.config_port import ConfigPort
from solver.domain.ports.outbound.datalog_port import DatalogPort
from solver.domain.ports.outbound.llm_port import LLMGeneratorPort
from solver.domain.ports.outbound.prompt_port import PromptPort
from solver.domain.ports.outbound.rag_port import DocRAGPort
from solver.domain.ports.outbound.sandbox_port import SandboxPort
from solver.domain.ports.outbound.serializer_port import SerializerPort
from solver.application.services.task_state_builder import TaskStateBuilder
from solver.domain.services.datalog_utils import DatalogUtils
from solver.domain.services.validation.order_key_extractor import extract_order_key_indexes
from solver.domain.services.error_classifier import ErrorClassifier
from solver.domain.services.validation import ResultComparator, SchemaEvaluator


_log = getLogger("solver.services.runner")


class SolverRunnerService(SolverRunnerPort):
    """Orchestratore batch della risoluzione del benchmark con supporto parallelo e thread-safe."""

    @staticmethod
    def _is_recipe_passed(task_res: TaskSolverResultDTO, key: str) -> bool:
        """Verifica se una determinata ricetta ha superato il confronto gold."""
        rec = task_res.query_phase.get(key)
        return bool(rec and rec.match_gold)

    def __init__(
        self,
        config: ConfigPort,
        llm: LLMGeneratorPort,
        sandbox: SandboxPort,
        datalog: DatalogPort,
        rag: DocRAGPort,
        serializer: SerializerPort,
        analytics: SolverAnalyticsPort | None = None,
        prompts: PromptPort | None = None,
    ) -> None:
        """Inietta le porte ed i servizi di dominio."""
        self._config = config
        self._llm = llm
        self._sandbox = sandbox
        self._datalog = datalog
        self._rag = rag
        self._serializer = serializer
        self._analytics = analytics
        self._prompts = prompts

        self._agent = SolverAgent(llm, sandbox, datalog, rag, prompts=prompts)
        self._classifier = ErrorClassifier()
        self._comparator = ResultComparator()
        self._schema_evaluator = SchemaEvaluator()
        self._state_builder = TaskStateBuilder()
        self._lock = Lock()

    def run_benchmark(
        self,
        benchmark_path: Path,
        recipes: list[str] | None = None,
        limit: int | None = None,
        model_role: str = "default",
        output_dir: Path | None = None,
        batch_size: int = 1,
    ) -> SolverRunDTO:
        """Carica un benchmark serializzato ed esegue la valutazione sequenziale o parallela."""
        if not benchmark_path.exists():
            raise BenchmarkFormatError(f"File benchmark '{benchmark_path}' non trovato.")

        benchmark_raw = orjson_loads(benchmark_path.read_bytes())
        tasks_data = benchmark_raw.get("tasks", [])
        if not tasks_data:
            raise BenchmarkFormatError("Il benchmark non contiene alcun task valido.")

        if limit and limit > 0:
            tasks_data = tasks_data[:limit]

        target_recipes = recipes or [
            RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value,
            RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value,
            RecipeType.TEXT_TO_SQL_ZERO_SHOT.value,
            RecipeType.TEXT_TO_DATALOG_RAG_CLINGO.value,
            RecipeType.SQL_TO_DATALOG_TRANSPILED.value,
        ]

        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        start_time = time()
        _log.info(
            "Avvio valutazione su %d task (batch_size=%d) con ricette: %s",
            len(tasks_data),
            batch_size,
            target_recipes,
        )

        task_results: list[TaskSolverResultDTO] = []

        if batch_size > 1:
            self._run_parallel(
                tasks_data,
                target_recipes,
                model_role,
                output_dir,
                run_id,
                str(benchmark_path),
                batch_size,
                task_results,
            )
        else:
            self._run_sequential(
                tasks_data,
                target_recipes,
                model_role,
                output_dir,
                run_id,
                str(benchmark_path),
                task_results,
            )

        elapsed = time() - start_time
        summary = self._compute_summary(tasks_data, task_results, elapsed)

        run_dto = SolverRunDTO(
            version=1,
            run_id=run_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            benchmark_source=str(benchmark_path),
            model_name=model_role,
            summary=summary,
            tasks=task_results,
        )

        if output_dir:
            saved_path = self._serializer.save_run(run_dto, output_dir)
            if self._analytics:
                try:
                    plots_dir = output_dir.parent / "plots" / saved_path.stem
                    self._analytics.analyze_run(saved_path, plots_dir)
                except (SolverException, OSError, ValueError, RuntimeError) as e:
                    _log.warning("Generazione automatica grafici per '%s' fallita: %s", run_id, e)

        return run_dto

    def _run_sequential(
        self,
        tasks_data: list[dict[str, Any]],
        target_recipes: list[str],
        model_role: str,
        output_dir: Path | None,
        run_id: str,
        benchmark_src: str,
        task_results: list[TaskSolverResultDTO],
    ) -> None:
        """Esegue la valutazione sequenziale con aggiornamento tqdm e salvataggio incrementale."""
        sql_passes = 0
        dl_passes = 0
        desc = "Risoluzione Benchmark (Sequenziale)"

        with tqdm(total=len(tasks_data), desc=desc, smoothing=0.1) as pbar:
            for task_idx, tdata in enumerate(tasks_data, 1):
                t_id = tdata.get("task_id", "")
                cat = tdata.get("category", "")
                pbar.set_postfix(
                    task=t_id,
                    cat=cat,
                    sql=f"{sql_passes}/{task_idx - 1}",
                    dl=f"{dl_passes}/{task_idx - 1}",
                )
                task_res = self._process_single_task(tdata, target_recipes, model_role)

                with self._lock:
                    task_results.append(task_res)
                    if self._is_recipe_passed(task_res, "text_to_sql_rag_sandbox_gold"):
                        sql_passes += 1
                    if self._is_recipe_passed(task_res, "text_to_datalog_rag_clingo_gold"):
                        dl_passes += 1

                self._save_incremental(
                    task_results,
                    tasks_data,
                    run_id,
                    benchmark_src,
                    model_role,
                    output_dir,
                )

                pbar.set_postfix(
                    task=t_id,
                    cat=cat,
                    sql=f"{sql_passes}/{task_idx}",
                    dl=f"{dl_passes}/{task_idx}",
                )
                pbar.update(1)

    def _run_parallel(
        self,
        tasks_data: list[dict[str, Any]],
        target_recipes: list[str],
        model_role: str,
        output_dir: Path | None,
        run_id: str,
        benchmark_src: str,
        batch_size: int,
        task_results: list[TaskSolverResultDTO],
    ) -> None:
        """Esegue la valutazione parallela in batch con ThreadPoolExecutor e Lock."""
        stats = {"sql_passes": 0, "dl_passes": 0, "completed": 0}
        desc = f"Risoluzione Benchmark (Parallel {batch_size})"

        with tqdm(total=len(tasks_data), desc=desc, smoothing=0.1) as pbar:
            executor = ThreadPoolExecutor(max_workers=batch_size)
            try:
                futures: dict[Future, dict[str, Any]] = {}
                task_iter = iter(tasks_data)
                self._fill_futures(
                    executor, futures, task_iter, batch_size, target_recipes, model_role
                )

                while futures:
                    done, _ = wait(list(futures.keys()), return_when=FIRST_COMPLETED)
                    for fut in done:
                        item = futures.pop(fut)
                        self._handle_completed_future(
                            fut,
                            item,
                            task_results,
                            tasks_data,
                            run_id,
                            benchmark_src,
                            model_role,
                            output_dir,
                            pbar,
                            stats,
                        )
                        self._fill_futures(
                            executor,
                            futures,
                            task_iter,
                            batch_size,
                            target_recipes,
                            model_role,
                        )
            finally:
                executor.shutdown(wait=True)

    def _fill_futures(
        self,
        executor: ThreadPoolExecutor,
        futures: dict[Future, dict[str, Any]],
        task_iter: Any,
        batch_size: int,
        target_recipes: list[str],
        model_role: str,
    ) -> None:
        """Riempie il pool dei futures fino al limite di concorrenza `batch_size`."""
        while len(futures) < batch_size:
            try:
                tdata = next(task_iter)
                fut = executor.submit(self._process_single_task, tdata, target_recipes, model_role)
                futures[fut] = tdata
            except StopIteration:
                break

    def _handle_completed_future(
        self,
        fut: Future,
        item: dict[str, Any],
        task_results: list[TaskSolverResultDTO],
        tasks_data: list[dict[str, Any]],
        run_id: str,
        benchmark_src: str,
        model_role: str,
        output_dir: Path | None,
        pbar: tqdm,
        stats: dict[str, int],
    ) -> None:
        """Gestisce il completamento di un task concorrente registrando i risultati."""
        try:
            task_res: TaskSolverResultDTO = fut.result()
            with self._lock:
                task_results.append(task_res)
                stats["completed"] += 1
                if self._is_recipe_passed(task_res, "text_to_sql_rag_sandbox_gold"):
                    stats["sql_passes"] += 1
                if self._is_recipe_passed(task_res, "text_to_datalog_rag_clingo_gold"):
                    stats["dl_passes"] += 1

                self._save_incremental(
                    task_results,
                    tasks_data,
                    run_id,
                    benchmark_src,
                    model_role,
                    output_dir,
                )

            pbar.set_postfix(
                task=task_res.task_id,
                cat=task_res.category,
                sql=f"{stats['sql_passes']}/{stats['completed']}",
                dl=f"{stats['dl_passes']}/{stats['completed']}",
            )
            pbar.update(1)
        except (
            SolverException,
            PgError,
            ParseError,
            ValidationError,
            ValueError,
            RuntimeError,
        ) as e:
            _log.error("Errore elaborazione task %s: %s", item.get("task_id"), e)

    def _save_incremental(
        self,
        task_results: list[TaskSolverResultDTO],
        tasks_data: list[dict[str, Any]],
        run_id: str,
        benchmark_src: str,
        model_role: str,
        output_dir: Path | None,
    ) -> None:
        """Salva atomicamente il report parziale su file per prevenire perdite di dati."""
        if not output_dir:
            return
        with self._lock:
            summary = self._compute_summary(tasks_data, task_results, 0.0)
            run_dto = SolverRunDTO(
                version=1,
                run_id=run_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
                benchmark_source=benchmark_src,
                model_name=model_role,
                summary=summary,
                tasks=list(task_results),
            )
            self._serializer.save_run(run_dto, output_dir)

    def _process_single_task(
        self,
        tdata: dict[str, Any],
        target_recipes: list[str],
        model_role: str,
    ) -> TaskSolverResultDTO:
        """Elabora un singolo task all'interno dei propri scope sandbox isolati."""
        state = self._state_builder.build(tdata)

        task_res = TaskSolverResultDTO(
            task_id=state.task_id,
            category=state.category,
            domain=state.domain,
            n_tables=state.n_tables,
            sql_features=state.sql_features,
            twists=state.twists,
            difficulty_label=state.difficulty_label,
            story=state.story,
            question=state.question,
        )

        if RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value in target_recipes:
            task_res.schema_phase = self._eval_schema_stage(state, model_role)

        self._eval_gold_schema_queries(state, target_recipes, model_role, task_res)
        self._eval_generated_schema_queries(state, target_recipes, model_role, task_res)

        return task_res

    def _eval_gold_schema_queries(
        self,
        state: SolverTaskStateDTO,
        target_recipes: list[str],
        model_role: str,
        task_res: TaskSolverResultDTO,
    ) -> None:
        """Esegue le ricette di query nello schema sandbox popolato con dati gold."""
        with self._sandbox.task_scope() as gold_schema:
            state.sandbox_schema = gold_schema
            if state.gold_schema_ddl:
                self._sandbox.execute_ddl(gold_schema, state.gold_schema_ddl)
            if state.gold_data_inserts:
                self._sandbox.execute_inserts(gold_schema, state.gold_data_inserts)

            for recipe_name in target_recipes:
                if recipe_name == RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value:
                    continue

                q_gold = self._eval_query_recipe(
                    recipe_name, state, SchemaSource.GOLD.value, model_role, task_res=task_res
                )
                task_res.query_phase[f"{recipe_name}_gold"] = q_gold

    def _eval_generated_schema_queries(
        self,
        state: SolverTaskStateDTO,
        target_recipes: list[str],
        model_role: str,
        task_res: TaskSolverResultDTO,
    ) -> None:
        """Esegue le ricette di query nello schema generato dal modello se valido."""
        if not state.generated_schema_ddl:
            return

        with self._sandbox.task_scope() as gen_schema:
            with suppress(Exception):
                self._sandbox.execute_ddl(gen_schema, state.generated_schema_ddl)
                if state.gold_data_inserts:
                    self._populate_generated_schema_safe(
                        gen_schema, state.generated_schema_ddl, state.gold_data_inserts
                    )

            original_schema = state.sandbox_schema
            state.sandbox_schema = gen_schema
            try:
                for recipe_name in target_recipes:
                    if recipe_name == RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value:
                        continue

                    q_gen = self._eval_query_recipe(
                        recipe_name,
                        state,
                        SchemaSource.GENERATED.value,
                        model_role,
                        task_res=task_res,
                    )
                    task_res.query_phase[f"{recipe_name}_generated"] = q_gen
            finally:
                state.sandbox_schema = original_schema

    def _populate_generated_schema_safe(  # noqa: C901, PLR0912
        self, gen_schema: str, gen_ddl: str, inserts_sql: str
    ) -> None:
        """Popola lo schema generato filtrando righe e colonne compatibili (Stadio 3 della tesi)."""
        if not inserts_sql or not gen_ddl:
            return
        gen_schemas = DatalogUtils.extract_schema_from_ddl(gen_ddl)
        if not gen_schemas:
            return
        try:
            parsed = sqlglot_parse(inserts_sql, read="postgres")
            for stmt in parsed:
                if not isinstance(stmt, exp.Insert):
                    continue
                tbl = stmt.find(exp.Table)
                if not tbl:
                    continue
                tbl_name = tbl.name.lower()
                if tbl_name not in gen_schemas:
                    continue

                gen_cols = set(gen_schemas[tbl_name])
                explicit_cols = (
                    [c.name.lower() for c in stmt.this.expressions]
                    if isinstance(stmt.this, exp.Schema)
                    else []
                )

                if explicit_cols and isinstance(stmt.expression, exp.Values):
                    valid_indices = [i for i, c in enumerate(explicit_cols) if c in gen_cols]
                    if not valid_indices:
                        continue
                    new_cols = [exp.to_column(explicit_cols[i]) for i in valid_indices]
                    new_schema = exp.Schema(
                        this=exp.Table(this=exp.to_identifier(tbl_name)), expressions=new_cols
                    )
                    new_tuples = []
                    for tup in stmt.expression.expressions:
                        if isinstance(tup, exp.Tuple):
                            new_vals = [
                                tup.expressions[i]
                                for i in valid_indices
                                if i < len(tup.expressions)
                            ]
                            new_tuples.append(exp.Tuple(expressions=new_vals))
                    if new_tuples:
                        filtered_stmt = exp.Insert(
                            this=new_schema, expression=exp.Values(expressions=new_tuples)
                        )
                        with suppress(PgError, SandboxSolverError, ValueError, TypeError):
                            self._sandbox.execute_inserts(
                                gen_schema, filtered_stmt.sql(dialect="postgres")
                            )
                else:
                    with suppress(PgError, SandboxSolverError, ValueError, TypeError):
                        self._sandbox.execute_inserts(gen_schema, stmt.sql(dialect="postgres"))
        except (ParseError, TokenError, PgError, ValueError, TypeError):
            pass

    def _eval_schema_stage(self, state: SolverTaskStateDTO, model_role: str) -> RecipeResultDTO:
        """Esegue e convalida lo Stage 1 (Text-to-Schema) con metriche Text2Schema e SA."""
        with self._sandbox.task_scope() as stage_schema:
            original_schema = state.sandbox_schema
            state.sandbox_schema = stage_schema
            try:
                s_res = self._agent.solve_recipe(
                    recipe=RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value,
                    state=state,
                    chain_role=model_role,
                    max_iterations=self._config.solver_max_tool_iterations(),
                )
                if s_res.generated_code:
                    with self._sandbox.task_scope() as verify_schema:
                        self._sandbox.execute_ddl(verify_schema, s_res.generated_code)
                    state.generated_schema_ddl = s_res.generated_code

                    eval_res = self._schema_evaluator.evaluate(
                        state.gold_schema_ddl, s_res.generated_code
                    )
                    s_res.schema_f1 = eval_res.schema_f1
                    s_res.schema_accuracy = eval_res.schema_accuracy
                    s_res.table_f1 = eval_res.table_f1
                    s_res.column_f1 = eval_res.column_f1
                    s_res.pk_f1 = eval_res.pk_f1
                    s_res.fk_f1 = eval_res.fk_f1
                    s_res.match_gold = eval_res.schema_accuracy == 1.0
                else:
                    s_res.match_gold = False
                    s_res.error_type = ErrorType.SYNTAX_ERROR.value
                    s_res.error_message = "Nessun codice DDL generato dal modello."
            except (SandboxSolverError, PgError, ParseError, ValueError, TypeError) as e:
                s_res.match_gold = False
                s_res.error_type = self._classifier.classify_postgres_error(str(e))
                s_res.error_message = str(e)
            finally:
                state.sandbox_schema = original_schema
            return s_res

    def _compute_summary(
        self,
        tasks_data: list[dict[str, Any]],
        task_results: list[TaskSolverResultDTO],
        elapsed: float,
    ) -> SolverRunSummaryDTO:
        """Calcola le aggregazioni statistiche per il sommario formale della run."""
        sql_react_passes = sum(
            1 for t in task_results if self._is_recipe_passed(t, "text_to_sql_rag_sandbox_gold")
        )
        sql_zero_passes = sum(
            1 for t in task_results if self._is_recipe_passed(t, "text_to_sql_zero_shot_gold")
        )
        dl_react_passes = sum(
            1 for t in task_results if self._is_recipe_passed(t, "text_to_datalog_rag_clingo_gold")
        )
        dl_trans_passes = sum(
            1 for t in task_results if self._is_recipe_passed(t, "sql_to_datalog_transpiled_gold")
        )

        sql_react_gen = sum(
            1
            for t in task_results
            if self._is_recipe_passed(t, "text_to_sql_rag_sandbox_generated")
        )
        dl_react_gen = sum(
            1
            for t in task_results
            if self._is_recipe_passed(t, "text_to_datalog_rag_clingo_generated")
        )

        total_evals = sum(len(t.query_phase) for t in task_results)
        denom = total_evals or 1
        one_shot = sum(
            1 for t in task_results for q in t.query_phase.values() if q.trace.is_one_shot
        )
        tools_used = sum(
            1 for t in task_results for q in t.query_phase.values() if not q.trace.is_one_shot
        )

        n_tasks = len(task_results) or 1
        gold_rates = [
            sql_react_passes / n_tasks,
            sql_zero_passes / n_tasks,
            dl_react_passes / n_tasks,
            dl_trans_passes / n_tasks,
        ]
        pass_rate_global = sum(gold_rates) / len(gold_rates)

        schema_tasks = [t for t in task_results if t.schema_phase is not None]
        n_schema_tasks = len(schema_tasks) or 1
        schema_accuracy = (
            sum(1 for t in schema_tasks if t.schema_phase and t.schema_phase.schema_accuracy == 1.0)
            / n_schema_tasks
        )
        schema_f1_mean = (
            sum(t.schema_phase.schema_f1 or 0.0 for t in schema_tasks if t.schema_phase)
            / n_schema_tasks
        )

        sql_gold_rate = sql_react_passes / n_tasks
        sql_gen_rate = sql_react_gen / n_tasks
        schema_gap = max(0.0, round(sql_gold_rate - sql_gen_rate, 4))

        return SolverRunSummaryDTO(
            total_tasks=len(tasks_data),
            tasks_evaluated=len(task_results),
            pass_rate_global=pass_rate_global,
            pass_rate_sql_rag_sandbox_gold=sql_react_passes / n_tasks,
            pass_rate_sql_zero_shot_gold=sql_zero_passes / n_tasks,
            pass_rate_datalog_rag_clingo_gold=dl_react_passes / n_tasks,
            pass_rate_sql_to_datalog_transpiled_gold=dl_trans_passes / n_tasks,
            pass_rate_sql_rag_sandbox_generated=sql_react_gen / n_tasks,
            pass_rate_datalog_rag_clingo_generated=dl_react_gen / n_tasks,
            schema_accuracy=round(schema_accuracy, 4),
            schema_f1_mean=round(schema_f1_mean, 4),
            schema_gap=schema_gap,
            one_shot_rate=one_shot / denom,
            tool_usage_rate=tools_used / denom,
            duration_seconds=round(elapsed, 2),
        )

    def _eval_query_recipe(
        self,
        recipe_name: str,
        state: SolverTaskStateDTO,
        schema_source: str,
        model_role: str,
        task_res: TaskSolverResultDTO | None = None,
    ) -> RecipeResultDTO:
        """Esegue la valutazione di una ricetta di query contro le risposte gold."""
        start_t = time()

        if recipe_name == RecipeType.SQL_TO_DATALOG_TRANSPILED.value:
            return self._eval_sql_to_datalog_transpiled(
                state, schema_source, model_role, start_t, task_res=task_res
            )

        try:
            q_res = self._agent.solve_recipe(
                recipe=recipe_name,
                state=state,
                schema_source=schema_source,
                chain_role=model_role,
                max_iterations=self._config.solver_max_tool_iterations(),
            )
        except (
            SolverException,
            PgError,
            ParseError,
            ValidationError,
            ValueError,
            RuntimeError,
        ) as e:
            _log.warning("Errore risoluzione ricetta %s task %s: %s", recipe_name, state.task_id, e)
            return RecipeResultDTO(
                recipe=recipe_name,
                schema_source=schema_source,
                generated_code="",
                match_gold=False,
                error_type=ErrorType.UNKNOWN_ERROR.value,
                error_message=str(e),
                duration_seconds=round(time() - start_t, 2),
            )

        q_res.duration_seconds = round(time() - start_t, 2)

        if recipe_name in (
            RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value,
            RecipeType.TEXT_TO_SQL_ZERO_SHOT.value,
        ):
            self._verify_sql_recipe(state, q_res)
        elif recipe_name == RecipeType.TEXT_TO_DATALOG_RAG_CLINGO.value:
            self._verify_datalog_recipe(state, q_res)

        return q_res

    def _eval_sql_to_datalog_transpiled(
        self,
        state: SolverTaskStateDTO,
        schema_source: str,
        model_role: str,
        start_t: float,
        task_res: TaskSolverResultDTO | None = None,
    ) -> RecipeResultDTO:
        """Genera la query SQL e la fa tradurre in Datalog dal modello.

        La traduzione e' interamente delegata all'LLM (i due paradigmi non
        ammettono una mappatura sintattica completa); la validita' e' comunque
        garantita dall'esecuzione su Clingo e dal confronto con il gold.
        """
        prev_key = f"{RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value}_{schema_source}"
        prev_res = task_res.query_phase.get(prev_key) if task_res else None

        if prev_res and prev_res.generated_code:
            intermediate_sql = prev_res.generated_code
            trace = prev_res.trace
        else:
            sql_res = self._agent.solve_recipe(
                recipe=RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value,
                state=state,
                schema_source=schema_source,
                chain_role=model_role,
                max_iterations=self._config.solver_max_tool_iterations(),
            )
            intermediate_sql = sql_res.generated_code
            trace = sql_res.trace

        active_ddl = (
            state.gold_schema_ddl
            if schema_source == SchemaSource.GOLD.value or not state.generated_schema_ddl
            else state.generated_schema_ddl
        )
        schemas = DatalogUtils.extract_schema_from_ddl(active_ddl)
        facts, scale, _precise = DatalogUtils.build_datalog_facts(state.gold_data_inserts, schemas)
        state.datalog_scale = scale

        q_res = RecipeResultDTO(
            recipe=RecipeType.SQL_TO_DATALOG_TRANSPILED.value,
            schema_source=schema_source,
            intermediate_sql=intermediate_sql,
            trace=trace,
            datalog_scale=scale,
            translation_mode="llm",
        )

        try:
            llm_res = self._agent.solve_recipe(
                recipe=RecipeType.SQL_TO_DATALOG_TRANSPILED.value,
                state=state,
                schema_source=schema_source,
                chain_role=model_role,
                max_iterations=self._config.solver_max_tool_iterations(),
                sql_to_translate=intermediate_sql,
            )
        except (
            SolverException,
            PgError,
            ParseError,
            ValidationError,
            ValueError,
            RuntimeError,
        ) as e:
            q_res.match_gold = False
            q_res.error_type = ErrorType.UNKNOWN_ERROR
            q_res.error_message = f"traduzione LLM non disponibile: {e}"
            q_res.duration_seconds = round(time() - start_t, 2)
            return q_res

        q_res.generated_code = llm_res.generated_code
        q_res.trace = llm_res.trace
        q_res.duration_seconds = round(time() - start_t, 2)
        self._verify_datalog_recipe(state, q_res, facts, scale)
        return q_res

    def _verify_sql_recipe(self, state: SolverTaskStateDTO, q_res: RecipeResultDTO) -> None:
        """Esegue e confronta la query SQL candidata nel sandbox Postgres."""
        try:
            t0 = time()
            cand_cols, cand_rows = self._sandbox.run_query(
                state.sandbox_schema, q_res.generated_code
            )
            q_res.execution_time_ms = round((time() - t0) * 1000.0, 3)
            is_match = self._comparator.compare(
                cand_rows,
                state.gold_rows,
                order_sensitive=state.order_sensitive,
                tie_keys=extract_order_key_indexes(state.gold_query, state.gold_columns),
                candidate_columns=cand_cols,
                gold_columns=state.gold_columns,
                allow_column_permutation=True,
            )
            q_res.match_gold = is_match
            if not is_match:
                q_res.error_type = self._classifier.classify_result_mismatch(
                    cand_rows, state.gold_rows, state.order_sensitive
                )
        except (SandboxSolverError, PgError, ValueError, TypeError) as e:
            q_res.match_gold = False
            q_res.error_type = self._classifier.classify_postgres_error(str(e))
            q_res.error_message = str(e)

    def _verify_datalog_recipe(
        self,
        state: SolverTaskStateDTO,
        q_res: RecipeResultDTO,
        facts: str | None = None,
        scale: int | None = None,
    ) -> None:
        """Esegue e confronta le regole Datalog candidate su Clingo.

        I modelli Datalog sono insiemi non ordinati: confronto a multinsieme con
        deduplica del gold e scaling unidirezionale alla scala dei fatti.
        """
        if facts is None or scale is None:
            active_ddl = state.gold_schema_ddl or state.generated_schema_ddl or ""
            schemas = DatalogUtils.extract_schema_from_ddl(active_ddl)
            facts, scale, _precise = DatalogUtils.build_datalog_facts(
                state.gold_data_inserts, schemas=schemas
            )
        t0 = time()
        success, cand_rows, err = self._datalog.run_datalog(
            facts, q_res.generated_code, predicate_name="query"
        )
        q_res.execution_time_ms = round((time() - t0) * 1000.0, 3)
        if not success:
            q_res.match_gold = False
            q_res.error_type = self._classifier.classify_clingo_error(err)
            q_res.error_message = err
            return

        is_match = self._comparator.compare(
            cand_rows,
            state.gold_rows,
            order_sensitive=False,
            allow_scaling=True,
            dedup_gold=True,
            scale=scale,
        )
        q_res.match_gold = is_match
        if not is_match:
            q_res.error_type = self._classifier.classify_result_mismatch(
                cand_rows, state.gold_rows, order_sensitive=False
            )
