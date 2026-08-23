"""Grafici 16-18: copertura della tassonomia e realismo dei volumi generati."""

from collections import Counter
from re import findall as re_findall
from typing import Any

import altair as alt

from bench.adapters.outbound.plotter.altair import builders, theme
from bench.adapters.outbound.plotter.altair.base import Plot


class HierarchyDistributionPlot(Plot):
    """16: distribuzione delle gerarchie relazionali degli schemi generati."""

    number = 16
    slug = "hierarchy_distribution"
    title = "Gerarchie relazionali degli schemi"
    subtitle = (
        "Numero di task per topologia dichiarata nella specifica (one-to-many, many-to-many, ...)."
    )

    _TOP = 12

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Top 12 topologie; la coda di topologie rare e' aggregata in un bucket."""
        counts = Counter(
            (task.get("spec") or {}).get("hierarchy")
            for task in tasks
            if (task.get("spec") or {}).get("hierarchy")
        )
        top = counts.most_common(self._TOP)
        rows_out = [{"gerarchia": key, "task": value} for key, value in top]
        tail_types = len(counts) - len(top)
        if tail_types > 0:
            tail_tasks = sum(value for _, value in counts.most_common()[self._TOP :])
            rows_out.append({"gerarchia": f"altre ({tail_types} topologie)", "task": tail_tasks})
        return rows_out

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali ordinate per frequenza."""
        return builders.hbar_values(
            rows,
            "gerarchia",
            "task",
            "N. task",
            reverse=True,
            accent_value=rows[0]["gerarchia"],
            order=[row["gerarchia"] for row in rows],
        )


class RowsPerTablePlot(Plot):
    """17: distribuzione delle righe generate per tabella (realismo dei volumi)."""

    number = 17
    slug = "rows_per_table_distribution"
    title = "Righe generate per tabella"
    subtitle = "Ogni punto e' una tabella di un database generato; il trattino indica la mediana."

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Una riga per tabella con la numerosita' effettivamente generata."""
        rows = []
        for task in tasks:
            profile = ((task.get("gold") or {}).get("data_profile") or {}).get("profile") or {}
            for stats in profile.values():
                row_count = stats.get("row_count")
                if row_count:
                    rows.append({"tabella": "tabelle", "righe": int(row_count)})
        return rows

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Strip orizzontale con mediana: la coda destra resta leggibile su scala log."""
        points = (
            alt.Chart(alt.Data(values=rows))
            .mark_circle(size=42, opacity=0.3, color=theme.ACCENT)
            .encode(
                x=alt.X(
                    "righe:Q",
                    scale=alt.Scale(type="log"),
                    title="Righe per tabella (scala log)",
                ),
                y=alt.Y("tabella:N", title=None, axis=None),
            )
        )
        medians = (
            points.transform_aggregate(mediana="median(righe)")
            .mark_tick(color=theme.MEDIAN, thickness=3, size=40)
            .encode(x="mediana:Q")
        )
        return (points + medians).properties(width=620, height=110)

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce mediana e estremi dei volumi generati."""
        if not rows:
            return None
        values = sorted(row["righe"] for row in rows)
        return (
            f"Mediana {values[len(values) // 2]} righe per tabella "
            f"(min {values[0]}, max {values[-1]} su {len(values)} tabelle)."
        )


_MIN_COMPOUND_FEATURES = 2


class QueryTypeFeatureCoveragePlot(Plot):
    """18: matrice di copertura tipo-query (Qxx) x feature SQL."""

    number = 18
    slug = "querytype_feature_coverage"
    title = "Copertura tipo-query x feature"
    subtitle = (
        "Solo i tipi-query che combinano piu' feature (l'incrocio interessante); "
        "i tipi a feature singola sono coperti dai grafici 01 e 09."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Coppie (tipo-query, feature) solo per i tipi che combinano piu' feature."""
        per_type: dict = {}
        for task in tasks:
            tokens = set(re_findall(r"Q\d+", task.get("category", "")))
            for q_token in tokens:
                per_type.setdefault(q_token, set()).update(
                    (task.get("spec") or {}).get("sql_features", [])
                )
        compound = {
            q for q, features in per_type.items() if len(features) >= _MIN_COMPOUND_FEATURES
        }
        counts: Counter = Counter()
        for task in tasks:
            for q_token in set(re_findall(r"Q\d+", task.get("category", ""))) & compound:
                for feature in (task.get("spec") or {}).get("sql_features", []):
                    counts[(q_token, feature)] += 1
        return [
            {"q_type": q_type, "feature": feature, "query": n}
            for (q_type, feature), n in counts.items()
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Heatmap con tipi-query in ascissa e feature in ordinata."""

        def natural_key(code: str) -> tuple[int, ...]:
            return tuple(int(part) for part in re_findall(r"\d+", code))

        q_types = sorted({row["q_type"] for row in rows}, key=natural_key)
        features = sorted(
            {row["feature"] for row in rows},
            key=lambda feature: -sum(row["query"] for row in rows if row["feature"] == feature),
        )
        return builders.heatmap(
            rows,
            "q_type",
            "feature",
            "query",
            width=1240,
            height=860,
            x_sort=q_types,
            y_sort=features,
            legend_title="N. query",
        )
