"""Template Method ``Plot`` per i grafici del solver.

Ogni grafico dichiara ``rows`` (run -> righe di dati), ``build`` (righe ->
codifica Altair) ed eventualmente ``evidence`` (frase sintetica). Il rendering
e' delegato a ``render``: nessun sottotipo tocca il filesystem o il tema.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import altair as alt

from solver.adapters.outbound.plotter.altair import theme
from solver.domain.models.solver import RecipeResultDTO, SolverRunDTO

GOLD_RECIPES = (
    "text_to_sql_rag_sandbox_gold",
    "text_to_sql_zero_shot_gold",
    "text_to_datalog_rag_clingo_gold",
    "sql_to_datalog_transpiled_gold",
)

RECIPE_LABELS = {
    "text_to_sql_rag_sandbox_gold": "SQL ReAct (RAG)",
    "text_to_sql_zero_shot_gold": "SQL zero-shot",
    "text_to_datalog_rag_clingo_gold": "Datalog ReAct",
    "sql_to_datalog_transpiled_gold": "Datalog transpiled",
    "text_to_schema_rag_sandbox": "Schema DDL",
}


class Plot(ABC):
    """Grafico dichiarativo della run del solver (Template Method)."""

    number: int = 0
    slug: str = ""
    title: str = ""
    subtitle: str = ""

    def filename(self) -> str:
        """Restituisce lo stem del file di output (senza estensione)."""
        return f"{self.number:02d}_{self.slug}"

    def render(self, run: SolverRunDTO, stem: Path) -> None:
        """Estrae le righe, costruisce il grafico temato e lo esporta in PNG+SVG.

        Una run senza dati per il grafico (es. ricetta mai valutata) non produce
        file: la cella mancante nel report e' piu' onesta di un grafico vuoto.
        """
        rows = self.rows(run)
        if not rows:
            return
        chart = theme.finalize(self.build(rows), self.title, self.subtitle, self.evidence(rows))
        theme.export(chart, stem)

    @abstractmethod
    def rows(self, run: SolverRunDTO) -> list[dict[str, Any]]:
        """Estrae le righe di dati dalla run (puro e deterministico)."""

    @abstractmethod
    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Codifica le righe nel grafico Altair."""

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:  # noqa: ARG002
        """Restituisce la frase di evidenza (default: nessuna)."""
        return None


def gold_results(run: SolverRunDTO) -> list[tuple[str, RecipeResultDTO]]:
    """Coppie (task_id, risultato) per tutte le ricette valutate sullo schema gold."""
    pairs: list[tuple[str, RecipeResultDTO]] = []
    for task in run.tasks:
        for key, result in task.query_phase.items():
            if key.endswith("_gold") and not key.startswith("text_to_schema"):
                pairs.append((task.task_id, result))
    return pairs


def recipe_pass_rows(
    run: SolverRunDTO, keys: tuple[str, ...] = GOLD_RECIPES
) -> list[dict[str, Any]]:
    """Pass rate per ricetta sullo schema gold: una riga per ricetta."""
    hits: dict[str, int] = dict.fromkeys(keys, 0)
    totals: dict[str, int] = dict.fromkeys(keys, 0)
    for task in run.tasks:
        for key in keys:
            result = task.query_phase.get(key)
            if result is None:
                continue
            totals[key] += 1
            hits[key] += int(result.match_gold)
    return [
        {
            "ricetta": RECIPE_LABELS.get(key, key),
            "pass_rate": hits[key] / totals[key] if totals[key] else 0.0,
            "task": totals[key],
        }
        for key in keys
        if totals[key]
    ]


def task_feature_rows(run: SolverRunDTO, key: str = GOLD_RECIPES[0]) -> list[dict[str, Any]]:
    """Una riga per coppia (task, feature) con l'esito della ricetta indicata."""
    rows: list[dict[str, Any]] = []
    for task in run.tasks:
        result = task.query_phase.get(key)
        if result is None:
            continue
        for feature in task.sql_features:
            rows.append({"feature": feature, "passato": int(result.match_gold)})
    return rows


def task_twist_rows(run: SolverRunDTO, key: str = GOLD_RECIPES[0]) -> list[dict[str, Any]]:
    """Una riga per coppia (task, tipo di twist) con l'esito della ricetta."""
    rows: list[dict[str, Any]] = []
    for task in run.tasks:
        result = task.query_phase.get(key)
        if result is None:
            continue
        for twist in task.twists:
            rows.append({"twist": twist, "passato": int(result.match_gold)})
    return rows
