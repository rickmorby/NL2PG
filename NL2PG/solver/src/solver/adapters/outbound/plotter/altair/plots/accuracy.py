"""Grafici di accuratezza: ricette, domini, difficolta' e dimensione schema."""

from typing import Any, ClassVar

import altair as alt

from solver.adapters.outbound.plotter.altair import base, builders, theme
from solver.domain.models.solver import SolverRunDTO


class RecipeAccuracyPlot(base.Plot):
    """01: pass rate per ricetta sullo schema gold (il quadro d'insieme)."""

    number = 1
    slug = "recipe_accuracy_gold"
    title = "Accuratezza delle ricette sullo schema gold"
    subtitle = "Quota di task risolti correttamente per ogni strategia di risoluzione."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe di pass rate per ricetta."""
        return base.recipe_pass_rows(run)

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali con accento sulla ricetta migliore."""
        best = max(rows, key=lambda row: row["pass_rate"])
        return builders.hbar_values(
            rows,
            "ricetta",
            "pass_rate",
            "Pass rate",
            reverse=True,
            fmt=".0%",
            domain=[0, 1],
            accent_value=best["ricetta"],
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Frase sintetica sulla ricetta dominante."""
        best = max(rows, key=lambda row: row["pass_rate"])
        return f"La ricetta migliore e' '{best['ricetta']}' ({best['pass_rate']:.0%})."


class GeneratedSchemaAccuracyPlot(base.Plot):
    """02: accuratezza sullo schema generato dal modello (generalizzazione)."""

    number = 2
    slug = "recipe_accuracy_generated"
    title = "Accuratezza sullo schema generato"
    subtitle = "Stesse ricette valutate sul DDL prodotto dal modello (fase di schema)."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Pass rate per ricetta sullo schema generato."""
        keys = tuple(key.replace("_gold", "_generated") for key in base.GOLD_RECIPES)
        return base.recipe_pass_rows(run, keys)

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali con accento sul migliore."""
        best = max(rows, key=lambda row: row["pass_rate"])
        return builders.hbar_values(
            rows,
            "ricetta",
            "pass_rate",
            "Pass rate",
            reverse=True,
            fmt=".0%",
            domain=[0, 1],
            accent_value=best["ricetta"],
        )


class DomainAccuracyPlot(base.Plot):
    """03: pass rate SQL per dominio di business (solo domini con n >= 5 task)."""

    number = 3
    slug = "accuracy_by_domain"
    title = "Accuratezza per dominio di business"
    subtitle = "Pass rate della ricetta SQL ReAct; solo domini con almeno 5 task."

    _MIN_TASKS: ClassVar[int] = 5

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe (dominio, pass rate, n) aggregate dai task."""
        stats: dict[str, list[int]] = {}
        for task in run.tasks:
            result = task.query_phase.get(base.GOLD_RECIPES[0])
            if result is None:
                continue
            stats.setdefault(task.domain, []).append(int(result.match_gold))
        return [
            {"dominio": domain, "pass_rate": sum(v) / len(v), "task": len(v)}
            for domain, v in sorted(stats.items(), key=lambda item: -len(item[1]))
            if len(v) >= self._MIN_TASKS
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali: etichetta con pass rate e numerosita'."""
        labeled = [{**row, "etichetta": f"{row['dominio']} (n={row['task']})"} for row in rows]
        worst = min(rows, key=lambda row: row["pass_rate"])
        return builders.hbar_values(
            labeled,
            "etichetta",
            "pass_rate",
            "Pass rate",
            reverse=False,
            fmt=".0%",
            domain=[0, 1],
            accent_color=theme.BAD,
            accent_value=f"{worst['dominio']} (n={worst['task']})",
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Frase sul dominio piu' ostico."""
        worst = min(rows, key=lambda row: row["pass_rate"])
        return f"Il dominio piu' ostico e' '{worst['dominio']}' ({worst['pass_rate']:.0%})."


class DifficultyAccuracyPlot(base.Plot):
    """04: pass rate per etichetta di difficolta' calibrata."""

    number = 4
    slug = "accuracy_by_difficulty"
    title = "Accuratezza per difficolta'"
    subtitle = "Pass rate della ricetta SQL ReAct per etichetta di calibrazione."

    _ORDER: ClassVar[list[str]] = ["easy", "medium", "hard"]

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe (difficolta', pass rate) aggregate."""
        stats: dict[str, list[int]] = {}
        for task in run.tasks:
            result = task.query_phase.get(base.GOLD_RECIPES[0])
            if result is None:
                continue
            stats.setdefault(task.difficulty_label, []).append(int(result.match_gold))
        return [
            {"difficolta": label, "pass_rate": sum(v) / len(v), "task": len(v)}
            for label, v in stats.items()
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre verticali discrete con valore sopra la colonna."""
        return builders.bars_discrete(
            rows,
            "difficolta",
            "pass_rate",
            "Difficolta'",
            "Pass rate",
            accent_value=max(rows, key=lambda row: row["pass_rate"])["difficolta"],
        )


class SchemaSizeAccuracyPlot(base.Plot):
    """05: distribuzione del pass rate per fascia di dimensione schema."""

    number = 5
    slug = "accuracy_by_schema_size"
    title = "Accuratezza per dimensione dello schema"
    subtitle = "Distribuzione dei pass rate individuali per fascia di tabelle; trattino = mediana."

    _BANDS: ClassVar[list[str]] = ["1-2", "3-4", "5-6", "7-12"]
    _EDGES: ClassVar[tuple] = ((2, "1-2"), (4, "3-4"), (6, "5-6"), (12, "7-12"))

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Una riga per task: fascia schema e esito della ricetta SQL."""
        rows = []
        for task in run.tasks:
            result = task.query_phase.get(base.GOLD_RECIPES[0])
            if result is None:
                continue
            rows.append(
                {
                    "fascia": self._band(task.n_tables),
                    "pass_rate": 1.0 if result.match_gold else 0.0,
                }
            )
        return rows

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Strip plot con mediane: la distribuzione reale, non la media che nasconde."""
        return builders.strip_median(
            rows,
            "fascia",
            "pass_rate",
            order=self._BANDS,
            xlabel="Tabelle nello schema",
            ylabel="Esito (1 = risolto)",
        )

    def _band(self, n_tables: int) -> str:
        """Fascia di appartenenza per numero di tabelle."""
        for edge, label in self._EDGES:
            if n_tables <= edge:
                return label
        return self._EDGES[-1][1]


class SchemaStageAccuracyPlot(base.Plot):
    """06: accuratezza della fase di generazione schema per difficolta'."""

    number = 6
    slug = "schema_stage_accuracy"
    title = "Fase di generazione schema"
    subtitle = "Quota di DDL validi prodotti dal modello, per difficolta' del task."

    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Righe (difficolta', schema valido) aggregate."""
        stats: dict[str, list[int]] = {}
        for task in run.tasks:
            if task.schema_phase is None:
                continue
            stats.setdefault(task.difficulty_label, []).append(int(task.schema_phase.match_gold))
        return [
            {"difficolta": label, "validi": sum(v) / len(v), "task": len(v)}
            for label, v in stats.items()
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre verticali discrete con quota di DDL validi."""
        return builders.bars_discrete(
            rows,
            "difficolta",
            "validi",
            "Difficolta'",
            "DDL validi",
            accent_value=max(rows, key=lambda row: row["validi"])["difficolta"],
        )
