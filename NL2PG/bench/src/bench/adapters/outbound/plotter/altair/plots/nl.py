"""Grafici 06-08: complessita' del linguaggio naturale (question e twist)."""

from collections import Counter
from typing import Any

import altair as alt

from bench.adapters.outbound.plotter.altair import builders
from bench.adapters.outbound.plotter.altair.base import (
    SCHEMA_BANDS,
    Plot,
    schema_band,
    twist_rows,
)


class QuestionComplexityPlot(Plot):
    """06: complessita' linguistica delle question per fascia di schema."""

    number = 6
    slug = "question_complexity_by_schema"
    title = "Complessita' linguistica vs dimensione schema"
    subtitle = (
        "Parole nella question per task, per fascia di numero di tabelle; "
        "il trattino indica la mediana."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta le parole di ogni question associandola alla fascia di schema."""
        return [
            {
                "band": schema_band((task.get("spec") or {}).get("n_tables", 0)),
                "parole": len((task.get("question") or "").split()),
            }
            for task in tasks
        ]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Punti + mediana: la distribuzione sostituisce il solo valore medio."""
        return builders.strip_median(
            rows, "band", "parole", SCHEMA_BANDS, "N. tabelle nello schema", "Parole nella question"
        )

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Confronta la lunghezza mediana tra la fascia piu' piccola e la piu' grande."""
        by_band = {
            band: sorted(row["parole"] for row in rows if row["band"] == band)
            for band in SCHEMA_BANDS
        }
        first, last = by_band[SCHEMA_BANDS[0]], by_band[SCHEMA_BANDS[-1]]
        if not first or not last:
            return None
        return (
            f"La mediana passa da {first[len(first) // 2]} parole (fascia 1-2) a "
            f"{last[len(last) // 2]} parole (fascia 7-12)."
        )


class TwistTypeFrequencyPlot(Plot):
    """07: frequenza dei disturbi semantici (twist) inseriti nelle question."""

    number = 7
    slug = "twist_type_frequency"
    title = "Frequenza dei disturbi semantici"
    subtitle = (
        "Regole di twist per tipo: misurano il disallineamento lessicale richiesto al solver."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta i tipi di twist su una riga per regola."""
        counts = Counter(row["twist_type"] for row in twist_rows(tasks))
        return [{"twist": key, "regole": value} for key, value in counts.most_common()]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali ordinate per frequenza."""
        return builders.hbar_values(rows, "twist", "regole", "N. regole", reverse=True)

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce il twist dominante."""
        if not rows:
            return None
        top = rows[0]
        return f"Il disturbo piu' frequente e' '{top['twist']}' ({top['regole']} regole)."


class JargonFrequencyPlot(Plot):
    """08: frequenza dei termini di gergo inseriti nei twist."""

    number = 8
    slug = "jargon_frequency"
    title = "Frequenza del gergo nei twist"
    subtitle = (
        "Valori obsoleti usati per mascherare lo schema e richiedere disambiguazione semantica."
    )

    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Conta i valori obsoleti (gergo) e conserva solo i sei piu' frequenti."""
        counts = Counter(row["obsolete_value"] for row in twist_rows(tasks))
        return [{"gergo": key, "occorrenze": value} for key, value in counts.most_common(6)]

    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Barre orizzontali: i termini gergali sono lunghi e restano leggibili."""
        return builders.hbar_values(rows, "gergo", "occorrenze", "Occorrenze", reverse=True)

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:
        """Restituisce il termine gergale dominante."""
        if not rows:
            return "Nessun termine di gergo registrato."
        top = rows[0]
        return f"Il termine piu' frequente e' '{top['gergo']}' ({top['occorrenze']} occorrenze)."
