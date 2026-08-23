"""Template Method ``Plot`` ed estrattori di righe condivisi.

Ogni grafico dichiara tre funzioni pure: ``rows`` (benchmark -> righe di dati),
``build`` (righe -> codifica Altair) ed eventualmente ``evidence`` (frase
sintetica calcolata sulle stesse righe). Il rendering e' delegato a ``render``:
nessun sottotipo tocca il filesystem o il tema. Gli estrattori in coda al
modulo sono riutilizzati dai moduli ``plots`` per evitare duplicazioni.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any

import altair as alt

from bench.adapters.outbound.plotter.altair import theme


class Plot(ABC):
    """Grafico dichiarativo del benchmark (Template Method)."""

    number: int = 0
    slug: str = ""
    title: str = ""
    subtitle: str = ""

    def filename(self) -> str:
        """Restituisce lo stem del file di output (senza estensione)."""
        return f"{self.number:02d}_{self.slug}"

    def render(self, tasks: list[dict[str, Any]], stem: Path) -> None:
        """Estrae le righe, costruisce il grafico temato e lo esporta in PNG+SVG."""
        rows = self.rows(tasks)
        chart = theme.finalize(self.build(rows), self.title, self.subtitle, self.evidence(rows))
        theme.export(chart, stem)

    @abstractmethod
    def rows(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Estrae le righe di dati dal benchmark (puro e deterministico)."""

    @abstractmethod
    def build(self, rows: list[dict[str, Any]]) -> alt.Chart:
        """Codifica le righe nel grafico Altair."""

    def evidence(self, rows: list[dict[str, Any]]) -> str | None:  # noqa: ARG002
        """Restituisce la frase di evidenza (default: nessuna)."""
        return None


def pass_rate(task: dict[str, Any]) -> float:
    """Restituisce il pass rate di calibrazione del task (0.0 se assente)."""
    value = (task.get("difficulty") or {}).get("calibration_pass_rate")
    return float(value) if value is not None else 0.0


def difficulty_label(task: dict[str, Any]) -> str:
    """Restituisce l'etichetta di difficolta' calibrata del task."""
    return (task.get("difficulty") or {}).get("label", "unknown")


SCHEMA_BANDS = ["1-2", "3-4", "5-6", "7-12"]
_BAND_EDGES = ((2, "1-2"), (4, "3-4"), (6, "5-6"), (12, "7-12"))
OUTCOMES = ["Passato", "Parziale", "Fallito"]
OUTCOME_COLORS = [theme.GOOD, theme.PARTIAL, theme.BAD]


def outcome_of(pass_rate_value: float) -> str:
    """Mappa il pass rate continuo sull'esito discreto osservato in calibrazione."""
    if pass_rate_value >= 1.0:
        return "Passato"
    if pass_rate_value > 0.0:
        return "Parziale"
    return "Fallito"


def feature_rate_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una riga per coppia (task, feature): {feature, pass_rate}."""
    return [
        {"feature": feature, "pass_rate": pass_rate(task)}
        for task in tasks
        for feature in (task.get("spec") or {}).get("sql_features", [])
    ]


def twist_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una riga per regola di twist: {twist_type, obsolete_value, pass_rate, label}."""
    rows: list[dict[str, Any]] = []
    for task in tasks:
        spec = task.get("spec") or {}
        pr = pass_rate(task)
        for rule in spec.get("twist_rules", []):
            rows.append(
                {
                    "twist_type": rule.get("twist_type", "unknown").lower(),
                    "obsolete_value": rule.get("obsolete_value") or "",
                    "pass_rate": pr,
                    "label": difficulty_label(task),
                }
            )
    return rows


def band_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una riga per task: {band, pass_rate, outcome, n_tables}."""
    return [
        {
            "band": schema_band((task.get("spec") or {}).get("n_tables", 0)),
            "pass_rate": pass_rate(task),
            "outcome": outcome_of(pass_rate(task)),
            "n_tables": (task.get("spec") or {}).get("n_tables", 0),
        }
        for task in tasks
    ]


def schema_band(n_tables: int) -> str:
    """Raggruppa il numero di tabelle nelle fasce usate nella calibrazione."""
    for edge, label in _BAND_EDGES:
        if n_tables <= edge:
            return label
    return _BAND_EDGES[-1][1]


def grouped_counts(
    rows: list[dict[str, Any]], key_field: str, group_field: str, top: int | None = None
) -> list[dict[str, Any]]:
    """Aggrega le righe per (chiave, gruppo) e le ordina per totale decrescente."""
    totals: defaultdict[str, int] = defaultdict(int)
    pairs: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        key = row[key_field]
        if not key:
            continue
        totals[key] += 1
        pairs[(key, row[group_field])] += 1
    keys = [k for k, _ in sorted(totals.items(), key=lambda item: -item[1])]
    if top is not None:
        keys = keys[:top]
    groups = sorted({row[group_field] for row in rows})
    return [
        {key_field: key, group_field: group, "task": pairs[(key, group)]}
        for key in keys
        for group in groups
    ]
