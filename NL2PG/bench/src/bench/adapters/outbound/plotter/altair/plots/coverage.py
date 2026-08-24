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

_QUERY_TYPE_NAMES = {
    1: "Single-table selection",
    2: "Scalar aggregation",
    3: "Top-N query",
    4: "Two-table join",
    5: "Grouped aggregation",
    6: "Conjunctive query",
    7: "Multi-table join",
    8: "Self-join",
    9: "Grouped aggregation + HAVING",
    10: "External knowledge grounding",
    11: "Nested subquery",
    12: "Correlated subquery",
    13: "EXISTS clause",
    14: "Set operation",
    15: "Non-recursive CTE",
    16: "Recursive query",
    17: "Window function",
    18: "LATERAL join",
    19: "Full outer join",
    20: "Right outer join",
    21: "Cross join",
    22: "DISTINCT ON",
    23: "Filtered aggregation",
    24: "Left outer join",
    25: "Natural join / USING",
    26: "Anti-join",
    27: "GROUPING SETS / ROLLUP / CUBE",
    28: "Range type query",
    29: "Aggregazione con DISTINCT",
    30: "Confronto tra row types",
    31: "Query su tipo ENUM",
    32: "VALUES inline",
    33: "Pattern matching",
    34: "Date/Time query",
    35: "Espressione condizionale (CASE)",
    36: "String manipulation",
    37: "Funzioni matematiche",
    38: "Quantified subquery",
    39: "BETWEEN",
    40: "IN condition",
    41: "IS NULL / IS NOT NULL",
    42: "Disjunctive query",
    43: "Sorting query",
    44: "Type casting",
    45: "Underspecification",
    46: "Relative time & durations",
    48: "SELECT DISTINCT",
    49: "IS DISTINCT FROM",
    50: "Boolean predicates",
    51: "OVERLAPS",
    52: "OFFSET / FETCH",
    53: "Ordered-set aggregate",
}
"""Nomi leggibili dei tipi-query; rispecchia ``config/categories.json``."""


def _human_query_type(q_token: str) -> str:
    """Restituisce il nome leggibile del tipo-query (il codice se sconosciuto)."""
    number = int(q_token[1:]) if q_token[1:].isdigit() else 0
    return _QUERY_TYPE_NAMES.get(number, q_token)


class QueryTypeFeatureCoveragePlot(Plot):
    """18: matrice di copertura tipo-query (Qxx) x feature SQL."""

    number = 18
    slug = "querytype_feature_coverage"
    title = "Copertura tipo-query x feature"
    _TOP = 12
    subtitle = (
        "Top 12 coppie dei tipi-query che combinano piu' feature; i tipi a feature "
        "singola sono coperti dai grafici 01 e 09."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Top 12 coppie (tipo-query, feature) dei tipi che combinano piu' feature."""
        per_type: dict = {}
        counts: Counter = Counter()
        for task in tasks:
            tokens = set(re_findall(r"Q\d+", task.get("category", "")))
            features = (task.get("spec") or {}).get("sql_features", [])
            for q_token in tokens:
                per_type.setdefault(q_token, set()).update(features)
                for feature in features:
                    counts[(q_token, feature)] += 1
        compound = {
            q
            for q, type_features in per_type.items()
            if len(type_features) >= _MIN_COMPOUND_FEATURES
        }
        pairs = sorted(
            ((q, f, n) for (q, f), n in counts.items() if q in compound),
            key=lambda item: -item[2],
        )
        labels = []
        for q_token, feature, n in pairs[: self._TOP]:
            name = _human_query_type(q_token)
            if feature.replace("_", " ") in name.lower():
                labels.append({"combinazione": name, "query": n})
            else:
                labels.append({"combinazione": f"{name} + {feature}", "query": n})
        return labels

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali: ogni coppia e' un dato, zero celle vuote."""
        return builders.hbar_values(
            rows,
            "combinazione",
            "query",
            "N. query",
            reverse=True,
            accent_value=rows[0]["combinazione"],
            label_limit=320,
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce la coppia dominante."""
        if not rows:
            return None
        top = rows[0]
        return f"La combinazione piu' frequente e' '{top['combinazione']}' ({top['query']} query)."
