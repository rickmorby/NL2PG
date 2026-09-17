"""Servizio di dominio puro per il calcolo delle metriche scientifiche del solver.

:author: Riccardo Morabito
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from solver.domain.models.analytics import ContingencyMatrixDTO, SolverAnalyticsDTO
from solver.domain.models.solver import SolverRunDTO, TaskSolverResultDTO


class SolverAnalyticsCalculator:
    """Calcolatore di dominio puro per le analisi statistiche e scientifiche del solver."""

    def compute_analytics(self, run_dto: SolverRunDTO) -> SolverAnalyticsDTO:
        """Calcola tutte le metriche di accuratezza, asimmetria, errori per operatore e twist."""
        tasks = run_dto.tasks
        total = len(tasks)
        if total == 0:
            return self._build_empty_analytics(run_dto)

        counts = {"s_ok": 0, "q_gold": 0, "q_gen": 0, "e2e": 0}
        matrix = {"q11": 0, "q10": 0, "q01": 0, "q00": 0}
        stats: dict[str, dict[Any, list[int]]] = {
            "recipes": defaultdict(list),
            "features": defaultdict(list),
            "twists": defaultdict(list),
            "twist_zero": defaultdict(list),
            "twist_count": defaultdict(list),
            "domains": defaultdict(list),
            "tables": defaultdict(list),
        }
        error_counts: Counter[str] = Counter()

        for t in tasks:
            self._evaluate_task_passes(t, counts, matrix)
            self._record_recipe_stats(t, stats["recipes"], error_counts)
            self._record_breakdowns(t, stats)

        return self._assemble_dto(run_dto, total, counts, matrix, stats, error_counts)

    def _build_empty_analytics(self, run_dto: SolverRunDTO) -> SolverAnalyticsDTO:
        """Restituisce un DTO vuoto in caso di assenza di task."""
        return SolverAnalyticsDTO(
            run_id=run_dto.run_id,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            model_name=run_dto.model_name,
        )

    @staticmethod
    def _evaluate_task_passes(
        t: TaskSolverResultDTO,
        counts: dict[str, int],
        matrix: dict[str, int],
    ) -> None:
        """Valuta il superamento delle fasi di schema e query popolando i conteggi."""
        s_ok = bool(t.schema_phase and t.schema_phase.match_gold)
        q_gold_rec = t.query_phase.get("text_to_sql_rag_sandbox_gold")
        q_gold_ok = bool(q_gold_rec and q_gold_rec.match_gold)
        q_gen_rec = t.query_phase.get("text_to_sql_rag_sandbox_generated")
        q_gen_ok = bool(q_gen_rec and q_gen_rec.match_gold)

        if s_ok:
            counts["s_ok"] += 1
        if q_gold_ok:
            counts["q_gold"] += 1
        if q_gen_ok:
            counts["q_gen"] += 1
        if s_ok and q_gen_ok:
            counts["e2e"] += 1

        if s_ok and q_gold_ok:
            matrix["q11"] += 1
        elif s_ok and not q_gold_ok:
            matrix["q10"] += 1
        elif not s_ok and q_gold_ok:
            matrix["q01"] += 1
        else:
            matrix["q00"] += 1

    @staticmethod
    def _record_recipe_stats(
        t: TaskSolverResultDTO,
        recipe_counts: dict[Any, list[int]],
        error_counts: Counter[str],
    ) -> None:
        """Registra i tassi di successo per ciascuna ricetta e raccoglie gli errori."""
        for r_name, r_res in t.query_phase.items():
            recipe_counts[r_name].append(1 if r_res.match_gold else 0)
            if not r_res.match_gold and r_res.error_type:
                error_counts[str(r_res.error_type.value)] += 1

    @staticmethod
    def _record_breakdowns(
        t: TaskSolverResultDTO,
        stats: dict[str, dict[Any, list[int]]],
    ) -> None:
        """Raggruppa le statistiche per feature SQL, twist, domini e numero tabelle."""
        q_react = t.query_phase.get("text_to_sql_rag_sandbox_gold")
        val = 1 if (q_react and q_react.match_gold) else 0
        q_zero = t.query_phase.get("text_to_sql_zero_shot_gold")
        zero_val = 1 if (q_zero and q_zero.match_gold) else 0

        for f in t.sql_features:
            stats["features"][f].append(val)

        twists = t.twists or ["baseline"]
        for tw in twists:
            stats["twists"][tw].append(val)
            stats["twist_zero"][tw].append(zero_val)

        stats["twist_count"][len(t.twists)].append(val)
        if t.domain:
            stats["domains"][t.domain].append(val)
        stats["tables"][t.n_tables].append(val)

    def _assemble_dto(
        self,
        run_dto: SolverRunDTO,
        total: int,
        counts: dict[str, int],
        matrix: dict[str, int],
        stats: dict[str, dict[Any, list[int]]],
        error_counts: Counter[str],
    ) -> SolverAnalyticsDTO:
        """Assembla il DTO finale con tutti i calcoli di accuratezza e boost."""
        a_schema = round(counts["s_ok"] / total, 4)
        a_gold = round(counts["q_gold"] / total, 4)
        a_gen = round(counts["q_gen"] / total, 4)
        a_e2e = round(counts["e2e"] / total, 4)
        cascade_delta = round(1.0 - (a_gen / a_gold), 4) if a_gold > 0 else 0.0
        schema_gap = max(0.0, round(a_gold - a_gen, 4))

        rag_boost = {}
        for tw, p_list in stats["twists"].items():
            react_acc = sum(p_list) / len(p_list)
            zero_list = stats["twist_zero"].get(tw, [])
            zero_acc = (sum(zero_list) / len(zero_list)) if zero_list else 0.0
            rag_boost[tw] = round(react_acc - zero_acc, 4)

        return SolverAnalyticsDTO(
            run_id=run_dto.run_id,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            total_tasks=total,
            model_name=run_dto.model_name,
            schema_accuracy=a_schema,
            schema_gap=schema_gap,
            query_gold_accuracy=a_gold,
            query_generated_accuracy=a_gen,
            end_to_end_accuracy=a_e2e,
            cascade_error_delta=cascade_delta,
            contingency_matrix=ContingencyMatrixDTO(
                q11_both_success=matrix["q11"],
                q10_schema_ok_query_fail=matrix["q10"],
                q01_schema_fail_query_ok=matrix["q01"],
                q00_both_fail=matrix["q00"],
            ),
            recipe_accuracies={
                k: round(sum(v) / len(v), 4) for k, v in stats["recipes"].items() if v
            },
            error_rates_by_sql_feature={
                k: round(1.0 - (sum(v) / len(v)), 4) for k, v in stats["features"].items() if v
            },
            error_rates_by_twist_type={
                k: round(1.0 - (sum(v) / len(v)), 4) for k, v in stats["twists"].items() if v
            },
            accuracy_by_twist_count={
                k: round(sum(v) / len(v), 4) for k, v in stats["twist_count"].items() if v
            },
            accuracy_by_domain={
                k: round(sum(v) / len(v), 4) for k, v in stats["domains"].items() if v
            },
            accuracy_by_table_count={
                k: round(sum(v) / len(v), 4) for k, v in stats["tables"].items() if v
            },
            error_taxonomy_counts=dict(error_counts),
            rag_boost_by_twist=rag_boost,
        )
