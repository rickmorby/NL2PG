"""Forme grafiche condivise: una sola implementazione per ogni pattern ricorrente.

Le funzioni accettano righe di dati gia' estratte (liste di dict) e restituiscono
``alt.Chart`` non ancora titolati (il titolo applica ``finalize``). Seguono la
documentazione ufficiale Altair: ``alt.Step`` per l'altezza per categoria,
``yOffset`` per le barre raggruppate, ``stack("normalize")`` per le quote,
heatmap layered con ``alt.when`` per il contrasto del testo.
"""

from collections import Counter
from typing import Any

import altair as alt

from bench.adapters.outbound.plotter.altair import theme


def _data(rows: list[dict[str, Any]]) -> alt.Data:
    """Crea la sorgente dati inline (nessuna dipendenza da pandas)."""
    return alt.Data(values=rows)


def hbar_values(
    rows: list[dict[str, Any]],
    cat: str,
    val: str,
    xlabel: str,
    *,
    width: int = 620,
    domain: list[float] | None = None,
    reverse: bool = False,
    fmt: str = ".0f",
    accent_value: str | None = None,
    accent_color: str = theme.ACCENT,
    order: list[str] | None = None,
) -> alt.Chart:
    """Barre orizzontali ordinate per valore con etichetta a fine barra.

    Con ``reverse`` il massimo appare in alto (ordinamento decrescente); il
    default mette il minimo in alto, utile per i pass rate (peggio prima).
    Con ``accent_value`` le barre diventano neutre e solo il dato nominato
    assume il colore saturo (principio dell'accento). ``order`` impone un
    ordinamento esplicito delle categorie (es. bucket aggregato in fondo).
    """
    x_scale = alt.Scale(domain=domain) if domain else alt.Scale(zero=True)
    y_sort = order if order is not None else ("-x" if reverse else "x")
    y_encoding = alt.Y(f"{cat}:N", sort=y_sort, title=None)
    color_encoding = (
        alt.condition(
            f"datum.{cat} === '{accent_value}'",
            alt.value(accent_color),
            alt.value(theme.NEUTRAL),
        )
        if accent_value is not None
        else alt.value(theme.ACCENT)
    )
    bars = (
        alt.Chart(_data(rows))
        .mark_bar()
        .encode(
            x=alt.X(f"{val}:Q", title=xlabel, scale=x_scale),
            y=y_encoding,
            color=color_encoding,
        )
        .properties(width=width, height=alt.Step(22))
    )
    labels = (
        alt.Chart(_data(rows))
        .mark_text(align="left", dx=5, fontSize=11, color=theme.LABEL)
        .encode(
            x=alt.X(f"{val}:Q", title=xlabel, scale=x_scale),
            y=y_encoding,
            text=alt.Text(f"{val}:Q", format=fmt),
        )
    )
    return bars + labels


def bars_discrete(
    rows: list[dict[str, Any]],
    cat: str,
    val: str,
    xlabel: str,
    ylabel: str,
    *,
    width: int = 520,
    height: int = 320,
    accent_value: str | None = None,
) -> alt.Chart:
    """Barre verticali per pochi valori ordinali, con valore sopra la colonna.

    Con ``accent_value`` solo la colonna nominata assume il colore saturo.
    """
    color_encoding = (
        alt.condition(
            f"datum.{cat} === '{accent_value}'",
            alt.value(theme.ACCENT),
            alt.value(theme.NEUTRAL),
        )
        if accent_value is not None
        else alt.value(theme.ACCENT)
    )
    bars = (
        alt.Chart(_data(rows))
        .mark_bar()
        .encode(
            x=alt.X(
                f"{cat}:O",
                sort="ascending",
                title=xlabel,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y(f"{val}:Q", title=ylabel),
            color=color_encoding,
        )
        .properties(width=width, height=height)
    )
    labels = (
        alt.Chart(_data(rows))
        .mark_text(baseline="bottom", dy=-4, fontSize=11, color=theme.LABEL)
        .encode(
            x=alt.X(f"{cat}:O", sort="ascending", title=xlabel),
            y=alt.Y(f"{val}:Q", title=ylabel),
            text=alt.Text(f"{val}:Q", format=".0f"),
        )
    )
    return bars + labels


_TEXT_PX_PER_CHAR = 6.5
_TEXT_PADDING_PX = 10
"""Stima di ingombro testo (font 11): decide se l'etichetta entra nel segmento."""
"""Quota minima perché l'etichetta entri nel segmento; sotto, va fuori con nota."""


def stacked_share(
    rows: list[dict[str, Any]],
    cat: str,
    status: str,
    order: list[str],
    colors: list[str],
    xlabel: str,
    *,
    cat_order: list[str] | None = None,
    width: int = 620,
) -> alt.Chart:
    """Barre orizzontali al 100%: composizione di esiti per categoria.

    Le categorie devono gia' esporre ``n`` nel testo dell'etichetta: la quota
    percentuale e' immediata, la numerosita' e' dichiarata a fianco. ``order``
    e ``colors`` descrivono la scala degli esiti; ``cat_order`` l'ordine delle
    categorie sull'asse (default: alfabetico).
    """
    counts = Counter((row[cat], row[status]) for row in rows)
    totals = Counter(row[cat] for row in rows)
    inside_rows, outside_rows = [], []
    for category in totals:
        cumulative = 0
        for status_value in order:
            segment = counts.get((category, status_value), 0)
            if not segment:
                continue
            share = segment / totals[category]
            entry = {
                cat: category,
                "center": (cumulative + segment / 2) / totals[category],
                "pct": share,
            }
            label = f"{share:.0%}"
            fits = share * width >= len(label) * _TEXT_PX_PER_CHAR + _TEXT_PADDING_PX
            if fits:
                inside_rows.append(entry)
            else:
                outside_rows.append({**entry, "nota": f"{status_value} {label}"})
            cumulative += segment
    bars = (
        alt.Chart(_data(rows))
        .mark_bar(size=30)
        .encode(
            x=alt.X("count():Q", stack="normalize", title=xlabel),
            y=alt.Y(f"{cat}:N", sort=cat_order, title=None),
            color=alt.Color(
                f"{status}:N",
                scale=alt.Scale(domain=order, range=colors),
                title=None,
            ).legend(orient="top"),
        )
        .properties(width=width, height=alt.Step(52))
    )
    inside = (
        alt.Chart(_data(inside_rows))
        .mark_text(fontSize=11)
        .encode(
            x=alt.X(
                "center:Q",
                scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False),
            ),
            y=alt.Y(f"{cat}:N", sort=cat_order, title=None),
            text=alt.Text("pct:Q", format=".0%"),
            color=alt.condition("datum.pct > 0.25", alt.value("#FFFFFF"), alt.value(theme.LABEL)),
        )
    )
    outside = (
        alt.Chart(_data(outside_rows))
        .mark_text(baseline="bottom", dy=-24, fontSize=11, fontWeight="bold", color=theme.LABEL)
        .encode(
            x=alt.X(
                "center:Q",
                scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False),
            ),
            y=alt.Y(f"{cat}:N", sort=cat_order, title=None),
            text=alt.Text("nota:N"),
        )
    )
    return bars + inside + outside


def grouped_hbar(
    rows: list[dict[str, Any]],
    cat: str,
    val: str,
    color: str,
    order: list[str],
    colors: list[str],
    xlabel: str,
    *,
    width: int = 620,
) -> alt.Chart:
    """Barre orizzontali raggruppate: due serie affiancate per categoria (yOffset)."""
    bars = (
        alt.Chart(_data(rows))
        .mark_bar()
        .encode(
            x=alt.X(f"{val}:Q", title=xlabel),
            y=alt.Y(f"{cat}:N", sort="-x", title=None),
            yOffset=alt.YOffset(f"{color}:N", sort=order, title=None),
            color=alt.Color(f"{color}:N", scale=alt.Scale(domain=order, range=colors), title=None),
        )
        .properties(width=width, height=alt.Step(20))
    )
    labels = (
        alt.Chart(_data(rows))
        .mark_text(align="left", dx=5, fontSize=11, color=theme.LABEL)
        .encode(
            x=alt.X(f"{val}:Q", title=xlabel),
            y=alt.Y(f"{cat}:N", sort="-x", title=None),
            yOffset=alt.YOffset(f"{color}:N", sort=order, title=None),
            text=alt.Text(f"{val}:Q", format=".0f"),
        )
    )
    return bars + labels


def strip_median(
    rows: list[dict[str, Any]],
    cat: str,
    val: str,
    order: list[str],
    xlabel: str,
    ylabel: str,
    *,
    width: int = 560,
    height: int = 340,
) -> alt.Chart:
    """Punti per osservazione + trattino di mediana: la distribuzione reale."""
    points = (
        alt.Chart(_data(rows))
        .mark_circle(size=48, opacity=0.35, color=theme.ACCENT)
        .encode(
            x=alt.X(f"{cat}:N", sort=order, title=xlabel, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{val}:Q", title=ylabel),
        )
    )
    medians = (
        points.transform_aggregate(median=f"median({val})", groupby=[cat])
        .mark_tick(color=theme.MEDIAN, thickness=3, size=34)
        .encode(y=alt.Y("median:Q", title=ylabel))
    )
    median_labels = (
        points.transform_aggregate(median=f"median({val})", groupby=[cat])
        .mark_text(align="left", dx=22, dy=4, fontSize=11, color=theme.LABEL)
        .encode(
            x=alt.X(f"{cat}:N", sort=order, title=xlabel),
            y=alt.Y("median:Q", title=ylabel),
            text=alt.Text("median:Q", format=".1f"),
        )
    )
    return (points + medians + median_labels).properties(width=width, height=height)


def heatmap(
    rows: list[dict[str, Any]],
    x: str,
    y: str,
    val: str,
    *,
    width: int = 640,
    height: int | None = None,
    x_sort: list[str] | None = None,
    y_sort: list[str] | None = None,
    legend_title: str = "",
) -> alt.Chart:
    """Mappa di calore layered con etichette: solo le celle osservate.

    Le righe con valore nullo non devono essere passate: la cella mancante
    comunica l'assenza meglio di uno zero colorato. Il testo inverte il colore
    sulle celle piu' scure (soglia a metà del massimo osservato).
    """
    n_y = len({row[y] for row in rows})
    height = height or max(200, 20 * n_y + 40)
    max_value = max((row[val] for row in rows), default=0)
    base = alt.Chart(_data(rows)).encode(
        x=alt.X(
            f"{x}:N",
            sort=x_sort,
            title=None,
            axis=alt.Axis(labelAngle=-45, labelAlign="right"),
        ),
        y=alt.Y(f"{y}:N", sort=y_sort, title=None),
    )
    rect = base.mark_rect().encode(
        color=alt.Color(
            f"{val}:Q",
            scale=alt.Scale(scheme="blues"),
            title=legend_title or None,
        ).legend(orient="right")
    )
    text = base.mark_text(fontSize=10).encode(
        text=alt.Text(f"{val}:Q"),
        color=alt.when(alt.datum[val] > max_value / 2)
        .then(alt.value("#FFFFFF"))
        .otherwise(alt.value("#1A1A1A")),
    )
    return (rect + text).properties(width=width, height=height)


def line_points(
    rows: list[dict[str, Any]],
    cat: str,
    val: str,
    xlabel: str,
    ylabel: str,
    *,
    order: list[str] | None = None,
    width: int = 560,
    height: int = 340,
) -> alt.Chart:
    """Linea con punti marcati per trend su variabile ordinale piccola."""
    line = (
        alt.Chart(_data(rows))
        .mark_line(point=True, color=theme.ACCENT, strokeWidth=2.5)
        .encode(
            x=alt.X(
                f"{cat}:O",
                sort=order or "ascending",
                title=xlabel,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y(f"{val}:Q", title=ylabel, scale=alt.Scale(domain=[0, 1.02])),
        )
        .properties(width=width, height=height)
    )
    labels = (
        alt.Chart(_data(rows))
        .mark_text(baseline="bottom", dy=-8, fontSize=11, color=theme.LABEL)
        .encode(
            x=alt.X(f"{cat}:O", sort=order or "ascending", title=xlabel),
            y=alt.Y(f"{val}:Q", title=ylabel, scale=alt.Scale(domain=[0, 1.02])),
            text=alt.Text(f"{val}:Q", format=".2f"),
        )
    )
    return line + labels
