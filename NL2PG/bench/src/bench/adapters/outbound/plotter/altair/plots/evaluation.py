"""Grafici 13-15: valutazione della calibrazione e proprieta' del gold."""

from collections import Counter
from typing import Any

import altair as alt

from bench.adapters.outbound.plotter.altair import builders, theme
from bench.adapters.outbound.plotter.altair.base import (
    OUTCOME_COLORS,
    OUTCOMES,
    Plot,
    difficulty_label,
    outcome_of,
    pass_rate,
)

_CARDINALITY_CAP = 15


class PassRateByDifficultyPlot(Plot):
    """13: composizione degli esiti di calibrazione per classe di difficolta'."""

    number = 13
    slug = "passrate_by_difficulty"
    title = "Esiti di calibrazione per classe di difficolta'"
    subtitle = "Quota di task per esito nelle due classi calibrate empiricamente."

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Una riga per task con esito discreto ed etichetta di difficolta'."""
        return [
            {"label": difficulty_label(task).capitalize(), "esito": outcome_of(pass_rate(task))}
            for task in tasks
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre al 100%: la bimodalita' reale sostituisce le due barre di media."""
        return builders.stacked_share(
            rows,
            "label",
            "esito",
            OUTCOMES,
            OUTCOME_COLORS,
            "Quota di task",
            cat_order=["Easy", "Hard"],
            width=760,
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Confronta la quota di successi tra easy e hard."""
        passed: Counter = Counter()
        total: Counter = Counter()
        for row in rows:
            total[row["label"]] += 1
            if row["esito"] == "Passato":
                passed[row["label"]] += 1
        if not total.get("Easy") or not total.get("Hard"):
            return None
        return (
            f"La scala e' calibrata: pass rate {passed['Easy'] / total['Easy']:.0%} su Easy, "
            f"{passed['Hard'] / total['Hard']:.0%} su Hard."
        )


class CriticByCalibrationOutcomePlot(Plot):
    """14: distribuzione del critic score per esito della calibrazione."""

    number = 14
    slug = "critic_by_calibration_outcome"
    title = "Critic score per esito di calibrazione"
    subtitle = "Giudizio del Critic per task; il trattino indica la mediana di ogni gruppo."

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Associa il critic score all'esito di calibrazione di ogni task."""
        rows = []
        for task in tasks:
            score = (task.get("difficulty") or {}).get("critic_score")
            if score is None:
                continue
            rows.append({"esito": outcome_of(pass_rate(task)), "score": float(score)})
        return rows

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Punti + mediana: mostra la distribuzione, non il solo confronto di medie."""
        return builders.strip_median(
            rows, "esito", "score", OUTCOMES, "Esito della calibrazione", "Critic score"
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce le mediane dei tre gruppi nell'ordine di visualizzazione."""
        medians = []
        for outcome in OUTCOMES:
            values = sorted(row["score"] for row in rows if row["esito"] == outcome)
            if values:
                medians.append(f"{outcome} {values[len(values) // 2]:.1f}")
        return "Mediane critic score: " + ", ".join(medians) + "." if medians else None


class GoldCardinalityPlot(Plot):
    """15: distribuzione della cardinalita' del risultato gold."""

    number = 15
    slug = "gold_cardinality_distribution"
    title = "Cardinalita' del risultato gold"
    subtitle = (
        f"Righe nel risultato atteso; le cardinalita' oltre {_CARDINALITY_CAP} sono aggregate."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta i task per cardinalita' del risultato, con bucket finale aperto."""

        def bucket(cardinality: int) -> str:
            return str(cardinality) if cardinality <= _CARDINALITY_CAP else f">{_CARDINALITY_CAP}"

        counts = Counter(
            bucket(len((task.get("gold") or {}).get("result", {}).get("rows", [])))
            for task in tasks
        )
        order = [str(n) for n in range(1, _CARDINALITY_CAP + 1)] + [f">{_CARDINALITY_CAP}"]
        return [{"cardinalita": key, "task": counts[key]} for key in order if counts.get(key)]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre verticali su asse ordinale esplicito (bucket finale in coda)."""
        return (
            alt.Chart(alt.Data(values=rows))
            .mark_bar(color=theme.ACCENT)
            .encode(
                x=alt.X(
                    "cardinalita:O",
                    sort=[row["cardinalita"] for row in rows],
                    title="Righe nel risultato gold",
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y("task:Q", title="N. task"),
            )
            .properties(width=620, height=320)
        )
