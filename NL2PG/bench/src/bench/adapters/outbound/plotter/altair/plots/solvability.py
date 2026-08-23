"""Grafici 09-12: risolvibilita' del solver in calibrazione (pass rate)."""

from collections import Counter, defaultdict
from typing import Any

import altair as alt

from bench.adapters.outbound.plotter.altair import builders
from bench.adapters.outbound.plotter.altair.base import (
    OUTCOME_COLORS,
    OUTCOMES,
    SCHEMA_BANDS,
    Plot,
    band_rows,
    feature_rate_rows,
    grouped_counts,
    twist_rows,
)


class FeaturePassRatePlot(Plot):
    """09: pass rate medio di calibrazione per feature SQL obbligatoria."""

    number = 9
    slug = "feature_passrate_impact"
    title = "Impatto delle feature SQL sulla risolvibilita'"
    subtitle = (
        "Pass rate medio in calibrazione; la numerosita' (n) e' dichiarata accanto a ogni feature."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggrega pass rate e numerosita' per feature, dal piu' ostico al piu' facile."""
        grouped: defaultdict[str, list[float]] = defaultdict(list)
        for row in feature_rate_rows(tasks):
            grouped[row["feature"]].append(row["pass_rate"])
        return [
            {
                "feature": f"{feature} (n={len(rates)})",
                "pass_rate": round(sum(rates) / len(rates), 3),
                "_name": feature,
            }
            for feature, rates in sorted(
                grouped.items(), key=lambda item: sum(item[1]) / len(item[1])
            )
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali su scala [0, 1]: il peggiore in alto, lettura immediata."""
        return builders.hbar_values(rows, "feature", "pass_rate", "Pass rate medio", domain=[0, 1])

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce la feature piu' ostica."""
        if not rows:
            return None
        worst = rows[0]
        return (
            f"L'operatore piu' ostico e' '{worst['_name']}' "
            f"(pass rate medio {worst['pass_rate']:.0%})."
        )


class TwistDegradationPlot(Plot):
    """10: degrado del pass rate al crescere del numero di twist per task."""

    number = 10
    slug = "twist_degradation"
    title = "Degrado della risolvibilita' vs numero di twist"
    subtitle = (
        "Pass rate medio per numero di twist per task; la numerosita' (n) e' dichiarata sull'asse."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggrega pass rate e numerosita' per numero di twist, in ordine crescente."""
        rates_by_n: defaultdict[int, list[float]] = defaultdict(list)
        for task in tasks:
            n_twists = len((task.get("spec") or {}).get("twist_rules", []))
            rates_by_n[n_twists].append(
                float((task.get("difficulty") or {}).get("calibration_pass_rate") or 0.0)
            )
        return [
            {
                "twists": f"{n} (n={len(rates)})",
                "pass_rate": round(sum(rates) / len(rates), 3),
            }
            for n, rates in sorted(rates_by_n.items())
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Linea con punti: il trend e' la forma giusta per una variabile ordinale."""
        return builders.line_points(
            rows,
            "twists",
            "pass_rate",
            "Twist per task (n = task per punto)",
            "Pass rate medio",
            order=[row["twists"] for row in rows],
            width=720,
        )


class TwistDifficultyPlot(Plot):
    """11: composizione della difficolta' per tipo di twist."""

    number = 11
    slug = "twist_vs_difficulty"
    title = "Twist vs classe di difficolta'"
    subtitle = "Task per tipo di twist e difficolta' calibrata; solo i tipi piu' frequenti."

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta i task per coppia (twist, difficolta') sui dieci twist principali."""
        rows = [
            row
            for row in twist_rows(tasks)
            if row["twist_type"] and row["label"] in {"easy", "hard"}
        ]
        rows = [{**row, "label": row["label"].capitalize()} for row in rows]
        return grouped_counts(rows, "twist_type", "label", top=10)

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre raggruppate orizzontali con le due serie affiancate per categoria."""
        return builders.grouped_hbar(
            rows,
            "twist_type",
            "task",
            "label",
            ["Easy", "Hard"],
            ["#59A14F", "#E15759"],
            "N. task",
        )


class PassRateBySchemaBandPlot(Plot):
    """12: composizione degli esiti di calibrazione per fascia di schema."""

    number = 12
    slug = "passrate_by_schema_band"
    title = "Esiti di calibrazione per fascia di schema"
    subtitle = (
        "Quota di task per esito (Passato / Parziale / Fallito); n = numerosita' della fascia."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Una riga per task con fascia annotata dalla numerosita' della fascia."""
        rows = band_rows(tasks)
        counts = Counter(row["band"] for row in rows)
        return [
            {"band": f"{row['band']} (n={counts[row['band']]})", "esito": row["outcome"]}
            for row in rows
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre al 100%: i tre esiti discreti sostituiscono la media fuorviante."""
        bands = [row["band"] for row in rows]
        ordered = list(dict.fromkeys(bands))
        ordered.sort(key=lambda label: SCHEMA_BANDS.index(label.rsplit(" (n=", 1)[0]))
        return builders.stacked_share(
            rows,
            "band",
            "esito",
            OUTCOMES,
            OUTCOME_COLORS,
            "Quota di task",
            cat_order=ordered,
            width=640,
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Confronta la quota di successi tra la fascia piu' piccola e la piu' grande."""
        passed = Counter()
        total = Counter()
        for row in rows:
            band = row["band"].rsplit(" (n=", 1)[0]
            total[band] += 1
            if row["esito"] == "Passato":
                passed[band] += 1
        first, last = SCHEMA_BANDS[0], SCHEMA_BANDS[-1]
        if not total[first] or not total[last]:
            return None
        return (
            f"La quota di task superati passa dal {passed[first] / total[first]:.0%} (fascia 1-2) "
            f"al {passed[last] / total[last]:.0%} (fascia 7-12)."
        )
