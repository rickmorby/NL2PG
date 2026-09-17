"""Grafici di impatto: twist, feature SQL, errori e velocita' di esecuzione."""

from collections import Counter
from typing import Any, ClassVar

import altair as alt

from solver.adapters.outbound.plotter.altair import base, builders, theme
from solver.domain.models.solver import SolverRunDTO

_MIN_SUPPORT = 5
_TOP_ERRORS = 12


class TwistImpactPlot(base.Plot):
    """07: pass rate per tipo di twist (i piu' ostici prima, accento rosso sul peggio)."""

    number = 7
    slug = "twist_impact"
    title = "Impatto dei twist sulla risolvibilita'"
    subtitle = "Pass rate della ricetta SQL ReAct per tipo di twist (solo n >= 5)."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe (twist, pass rate, n) con supporto minimo."""
        return self._rate_rows(base.task_twist_rows(run))

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali ordinate dal peggiore, accento rosso sul peggiore."""
        labeled = [{**row, "etichetta": f"{row['twist']} (n={row['n']})"} for row in rows]
        worst = rows[0]
        return builders.hbar_values(
            labeled,
            "etichetta",
            "pass_rate",
            "Pass rate",
            reverse=False,
            fmt=".0%",
            domain=[0, 1],
            accent_color=theme.BAD,
            accent_value=f"{worst['twist']} (n={worst['n']})",
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Frase sul twist piu' degradante."""
        if not rows:
            return None
        return f"Il twist piu' ostico e' '{rows[0]['twist']}' ({rows[0]['pass_rate']:.0%})."

    @staticmethod
    def _rate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggrega per chiave, filtra il supporto minimo e ordina per pass rate crescente."""
        return ImpactRows.rate_rows(rows, "twist")


class FeatureImpactPlot(base.Plot):
    """08: pass rate per feature SQL (le piu' ostiche prima)."""

    number = 8
    slug = "feature_impact"
    title = "Impatto delle feature SQL"
    subtitle = "Pass rate della ricetta SQL ReAct per feature richiesta (solo n >= 5)."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe (feature, pass rate, n) con supporto minimo."""
        return ImpactRows.rate_rows(base.task_feature_rows(run), "feature")

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali con accento rosso sulla feature peggiore."""
        labeled = [{**row, "etichetta": f"{row['feature']} (n={row['n']})"} for row in rows]
        worst = rows[0]
        return builders.hbar_values(
            labeled,
            "etichetta",
            "pass_rate",
            "Pass rate",
            reverse=False,
            fmt=".0%",
            domain=[0, 1],
            accent_color=theme.BAD,
            accent_value=f"{worst['feature']} (n={worst['n']})",
        )


class ErrorTaxonomyPlot(base.Plot):
    """09: tassonomia degli errori piu' frequenti sulle ricette fallite."""

    number = 9
    slug = "error_taxonomy"
    title = "Tassonomia degli errori"
    subtitle = "Errori piu' frequenti tra le valutazioni gold fallite (tutte le ricette)."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Conteggio degli errori per tipo, solo sulle ricette fallite."""
        counter: Counter[str] = Counter()
        for _task_id, result in base.gold_results(run):
            if result.match_gold or result.error_type is None:
                continue
            counter[str(result.error_type.value)] += 1
        top = counter.most_common(_TOP_ERRORS)
        return [{"errore": name, "occorrenze": count} for name, count in top]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali con accento sull'errore dominante."""
        accent = rows[0]["errore"] if rows else None
        return builders.hbar_values(
            rows,
            "errore",
            "occorrenze",
            "Occorrenze",
            reverse=True,
            accent_value=accent,
        )


class RecipeErrorHeatmapPlot(base.Plot):
    """10: mappa ricetta x tipo di errore (solo celle osservate)."""

    number = 10
    slug = "recipe_error_heatmap"
    title = "Errori per ricetta"
    subtitle = "Distribuzione dei tipi di errore sulle valutazioni gold fallite."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe (ricetta, errore, occorrenze) senza celle vuote."""
        counter: Counter[tuple[str, str]] = Counter()
        for _task_id, result in base.gold_results(run):
            if result.match_gold or result.error_type is None:
                continue
            recipe = base.RECIPE_LABELS.get(result.recipe, result.recipe)
            counter[(recipe, str(result.error_type.value))] += 1
        return [
            {"ricetta": recipe, "errore": error, "occorrenze": count}
            for (recipe, error), count in counter.items()
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Heatmap blues con conteggi diretti nelle celle."""
        return builders.heatmap(
            rows,
            "errore",
            "ricetta",
            "occorrenze",
            width=760,
            legend_title="N.",
        )


class TranslationModePlot(base.Plot):
    """11: composizione deterministico/fallback della traduzione SQL -> Datalog."""

    number = 11
    slug = "translation_mode_share"
    title = "Traduzione SQL -> Datalog: deterministica vs LLM"
    subtitle = "Composizione della ricetta transpiled per modalita' di traduzione effettiva."

    _MODES: ClassVar[list[str]] = ["deterministic", "llm_fallback"]
    _MODE_COLORS: ClassVar[list[str]] = [theme.GOOD, theme.SECOND]

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Una riga per esito della ricetta transpiled gold."""
        rows = []
        for task in run.tasks:
            result = task.query_phase.get("sql_to_datalog_transpiled_gold")
            if result is None or not result.translation_mode:
                continue
            rows.append({"modalita": result.translation_mode, "match": result.match_gold})
        return rows

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre al 100% con quote etichettate e legenda visibile."""
        return builders.stacked_share(
            rows,
            "modalita",
            "modalita",
            order=self._MODES,
            colors=self._MODE_COLORS,
            xlabel="Composizione della ricetta transpiled",
        )


class ExecutionSpeedPlot(base.Plot):
    """12: mediana dei tempi di esecuzione per ricetta (SQL engine vs Clingo)."""

    number = 12
    slug = "execution_speed"
    title = "Tempi di esecuzione per ricetta"
    subtitle = "Mediana dei tempi di esecuzione (ms) sulle valutazioni gold riuscite."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Mediana dei tempi per ricetta, solo sulle esecuzioni riuscite."""
        times: dict[str, list[float]] = {}
        for _task_id, result in base.gold_results(run):
            if not result.match_gold or result.execution_time_ms <= 0:
                continue
            times.setdefault(result.recipe, []).append(result.execution_time_ms)
        rows = []
        for recipe, values in times.items():
            ordered = sorted(values)
            median = ordered[len(ordered) // 2]
            rows.append({"ricetta": base.RECIPE_LABELS.get(recipe, recipe), "mediana_ms": median})
        return rows

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali con accento sulla ricetta piu' rapida."""
        fastest = min(rows, key=lambda row: row["mediana_ms"])
        return builders.hbar_values(
            rows,
            "ricetta",
            "mediana_ms",
            "Mediana (ms)",
            reverse=True,
            accent_value=fastest["ricetta"],
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Frase sulla ricetta piu' rapida."""
        fastest = min(rows, key=lambda row: row["mediana_ms"])
        return f"Il motore piu' rapido e' '{fastest['ricetta']}' ({fastest['mediana_ms']:.1f} ms)."


class ImpactRows:
    """Helper condiviso di aggregazione per twist e feature."""

    @staticmethod
    def rate_rows(
        rows: list[dict[str, Any]], key_field: str, minimum: int = _MIN_SUPPORT
    ) -> list[dict[str, Any]]:
        """Aggrega i passati per chiave, filtra il supporto e ordina dal peggiore."""
        stats: dict[str, list[int]] = {}
        for row in rows:
            stats.setdefault(row[key_field], []).append(int(row["passato"]))
        aggregated = [
            {key_field: key, "pass_rate": sum(v) / len(v), "n": len(v)}
            for key, v in stats.items()
            if len(v) >= minimum
        ]
        return sorted(aggregated, key=lambda row: row["pass_rate"])
