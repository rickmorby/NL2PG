"""Identita' visiva unificata dei grafici: tema registrato, titoli ed export.

Il tema segue il meccanismo ufficiale ``alt.theme.register``: tipografia sobria,
griglia chiara, palette di default colorblind-safe. ``finalize`` aggiunge solo il
blocco titolo/sottotitolo/evidenza; ``export`` produce PNG @2x e SVG vettoriale
byte-identici tra run grazie al motore offline vl-convert.
"""

from pathlib import Path

import altair as alt

ACCENT = "#4C78A8"
"""Colore della serie principale (blu Vega, leggibile su bianco)."""

SECOND = "#F58518"
"""Colore della serie secondaria (arancio: coppia colorblind-safe con ACCENT)."""

GOOD = "#59A14F"
BAD = "#E15759"
PARTIAL = "#F1CE63"
MEDIAN = "#3D3D3D"
GRID = "#E6E6E6"

_TEXT = "#444444"
_SUBTITLE = "#555555"


@alt.theme.register("nl2pg", enable=True)
def _nl2pg_theme() -> alt.theme.ThemeConfig:
    """Tema del benchmark: config Vega-Lite applicata a ogni grafico."""
    return {
        "config": {
            "font": "Segoe UI, Helvetica, Arial, sans-serif",
            "axisX": {
                "labelFontSize": 11,
                "titleFontSize": 12,
                "labelColor": _TEXT,
                "titleColor": _TEXT,
                "gridColor": GRID,
                "domainColor": GRID,
            },
            "axisY": {
                "labelFontSize": 11,
                "titleFontSize": 12,
                "labelColor": _TEXT,
                "titleColor": _TEXT,
                "gridColor": GRID,
                "domainColor": GRID,
            },
            "legend": {"labelFontSize": 11, "titleFontSize": 12, "orient": "top"},
            "title": {
                "fontSize": 17,
                "anchor": "start",
                "subtitleFontSize": 12,
                "subtitleColor": _SUBTITLE,
                "dy": -8,
            },
            "view": {"stroke": None},
        }
    }


def finalize(
    chart: alt.Chart,
    title: str,
    subtitle: str = "",
    evidence: str | None = None,
) -> alt.Chart:
    """Aggiunge il blocco titolo: sottotitolo metodologico ed eventuale evidenza.

    L'evidenza e' resa come ultima riga del sottotitolo, cosi' la frase sintetica
    condivide la stessa fonte e la stessa geometria del resto del titolo.
    """
    subs = [s for s in (subtitle, f"Evidenza: {evidence}" if evidence else None) if s]
    return chart.properties(title=alt.TitleParams(title, subtitle=subs))


def export(chart: alt.Chart, stem: Path) -> None:
    """Salva il grafico come PNG @2x e SVG vettoriale nella stessa directory."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    chart.save(str(stem) + ".png", scale_factor=2.0, engine="vl-convert")
    chart.save(str(stem) + ".svg", engine="vl-convert")
