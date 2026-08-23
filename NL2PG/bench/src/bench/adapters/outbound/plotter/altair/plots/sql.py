"""Grafici 01-05: copertura e complessita' del SQL generato nel benchmark."""

from collections import Counter
from typing import Any

import altair as alt
from sqlglot.errors import ParseError

from bench.adapters.outbound.plotter.altair import builders
from bench.adapters.outbound.plotter.altair.base import Plot, feature_rate_rows
from bench.domain.services.analytics.analytics_calculator import AnalyticsCalculator


def _counter_rows(values: list[Any], cat: str) -> list[dict[str, Any]]:
    """Aggrega i valori in righe {cat, occorrenze} ordinate per frequenza."""
    counts = Counter(v for v in values if v)
    return [{cat: key, "occorrenze": n} for key, n in counts.most_common()]


class SqlFeatureDistributionPlot(Plot):
    """01: frequenza delle feature SQL richieste nelle query gold."""

    number = 1
    slug = "sql_feature_distribution"
    title = "Copertura delle feature SQL"
    subtitle = "Numero di task che richiedono ciascun costrutto SQL nella query gold."

    _TOP = 20

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Top 20 feature piu' richieste; la coda e' aggregata in un bucket."""
        rows = feature_rate_rows(tasks)
        counts = Counter(row["feature"] for row in rows)
        top = counts.most_common(self._TOP)
        tail = len(counts) - len(top)
        rows_out = [{"feature": key, "task": value} for key, value in top]
        if tail > 0:
            rows_out.append(
                {
                    "feature": f"altre ({tail} feature)",
                    "task": sum(v for _, v in counts.most_common()[self._TOP :]),
                }
            )
        return rows_out

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali ordinate: 40+ categorie esigono l'asse Y testuale."""
        return builders.hbar_values(
            rows,
            "feature",
            "task",
            "N. task",
            accent_value=rows[0]["feature"],
            order=[row["feature"] for row in rows],
        )


class AstDepthDistributionPlot(Plot):
    """02: distribuzione della profondita' AST delle query gold."""

    number = 2
    slug = "ast_depth_distribution"
    title = "Profondita' AST delle query gold"
    subtitle = (
        "Profondita' massima dell'albero sintattico (sqlglot): proxy della complessita' di nesting."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Calcola la profondita' AST di ogni query gold valida."""
        calc = AnalyticsCalculator()
        depths = []
        for task in tasks:
            query = (task.get("gold") or {}).get("query", "")
            try:
                depths.append(calc.parse_depth(query))
            except ParseError:
                continue
        counts = Counter(depths)
        return [{"profondita": key, "query": value} for key, value in sorted(counts.items())]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre verticali: la scala ordinale dei livelli resta leggibile in orizzontale."""
        modal = max(rows, key=lambda row: row["query"])
        return builders.bars_discrete(
            rows,
            "profondita",
            "query",
            "Profondita' AST",
            "N. query",
            accent_value=modal["profondita"],
        )


class DomainDistributionPlot(Plot):
    """03: diversita' dei domini aziendali coperti dal benchmark."""

    number = 3
    slug = "domain_distribution"
    title = "Diversita' dei domini aziendali"
    subtitle = "Numero di task generati per dominio applicativo."

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta i task per dominio dichiarato nella specifica."""
        return _counter_rows([(task.get("spec") or {}).get("domain") for task in tasks], "dominio")

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali ordinate per frequenza."""
        return builders.hbar_values(
            rows,
            "dominio",
            "occorrenze",
            "N. task",
            reverse=True,
            accent_value=rows[0]["dominio"],
        )


class SchemaSizeDistributionPlot(Plot):
    """04: distribuzione della dimensione degli schemi (numero di tabelle)."""

    number = 4
    slug = "schema_size_distribution"
    title = "Dimensione degli schemi"
    subtitle = "Numero di tabelle relazionali per database generato."

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta i task per numero di tabelle dichiarato nella specifica."""
        counts = Counter((task.get("spec") or {}).get("n_tables", 0) for task in tasks)
        return [{"tabelle": key, "database": value} for key, value in sorted(counts.items())]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre verticali su scala ordinale: le fasce restano in ordine naturale."""
        modal = max(rows, key=lambda row: row["database"])
        return builders.bars_discrete(
            rows,
            "tabelle",
            "database",
            "N. tabelle",
            "N. database",
            accent_value=modal["tabelle"],
        )


class SqlFeatureCooccurrencePlot(Plot):
    """05: co-occorrenza delle feature SQL piu' frequenti (diagonale esclusa)."""

    number = 5
    slug = "sql_feature_cooccurrence"
    title = "Co-occorrenza dei costrutti SQL"
    subtitle = (
        "Quante query condividono due costrutti; le feature sulla diagonale "
        "sono escluse per confrontabilita'."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta le coppie (a<b) di feature sulle stesse query, sulle top 14 feature."""
        counts = Counter(row["feature"] for row in feature_rate_rows(tasks))
        top = [key for key, _ in counts.most_common(14)]
        top_set = set(top)
        pairs: Counter = Counter()
        for task in tasks:
            features = sorted(
                {f for f in (task.get("spec") or {}).get("sql_features", []) if f in top_set}
            )
            for i, a in enumerate(features):
                for b in features[i + 1 :]:
                    pairs[(a, b)] += 1
        return [{"a": a, "b": b, "query": n} for (a, b), n in pairs.items() if n > 0]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Heatmap senza diagonale e senza celle vuote: solo segnale reale."""
        return builders.heatmap(rows, "a", "b", "query", width=560, height=420)

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce la coppia di costrutti piu' frequente."""
        if not rows:
            return None
        best = max(rows, key=lambda row: row["query"])
        return (
            f"La combinazione piu' frequente e' '{best['a']}' con '{best['b']}' "
            f"({best['query']} query)."
        )
