"""Forme grafiche condivise: una sola implementazione per ogni pattern ricorrente.

Le funzioni accettano righe di dati gia' estratte (liste di dict) e restituiscono
``alt.Chart`` non ancora titolati (il titolo applica ``finalize``). Seguono la
documentazione ufficiale Altair: ``alt.Step`` per l'altezza per categoria,
``yOffset`` per le barre raggruppate, ``stack("normalize")`` per le quote,
heatmap layered con ``alt.when`` per il contrasto del testo.
"""

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
) -> alt.Chart:
    """Barre orizzontali ordinate per valore: la forma standard per molte categorie.

    Con ``reverse`` il massimo appare in alto (ordinamento decrescente); il
    default mette il minimo in alto, utile per i pass rate (peggio prima).
    """
    x_scale = alt.Scale(domain=domain) if domain else alt.Scale(zero=True)
    return (
        alt.Chart(_data(rows))
        .mark_bar(color=theme.ACCENT)
        .encode(
            x=alt.X(f"{val}:Q", title=xlabel, scale=x_scale),
            y=alt.Y(f"{cat}:N", sort="-x" if reverse else "x", title=None),
        )
        .properties(width=width, height=alt.Step(22))
    )


def bars_discrete(
    rows: list[dict[str, Any]],
    cat: str,
    val: str,
    xlabel: str,
    ylabel: str,
    *,
    width: int = 520,
    height: int = 320,
) -> alt.Chart:
    """Barre verticali per un piccolo numero di valori ordinali (etichette dritte)."""
    return (
        alt.Chart(_data(rows))
        .mark_bar(color=theme.ACCENT)
        .encode(
            x=alt.X(
                f"{cat}:O",
                sort="ascending",
                title=xlabel,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y(f"{val}:Q", title=ylabel),
        )
        .properties(width=width, height=height)
    )


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
    return (
        alt.Chart(_data(rows))
        .mark_bar()
        .encode(
            x=alt.X("count():Q", stack="normalize", title=xlabel),
            y=alt.Y(f"{cat}:N", sort=cat_order, title=None),
            color=alt.Color(
                f"{status}:N",
                scale=alt.Scale(domain=order, range=colors),
                title=None,
            ),
        )
        .properties(width=width, height=alt.Step(44))
    )


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
    return (
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
    return (points + medians).properties(width=width, height=height)


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
    return (
        alt.Chart(_data(rows))
        .mark_line(point=True, color=theme.ACCENT, strokeWidth=2.5)
        .encode(
            x=alt.X(f"{cat}:O", sort=order or "ascending", title=xlabel),
            y=alt.Y(f"{val}:Q", title=ylabel, scale=alt.Scale(domain=[0, 1.02])),
        )
        .properties(width=width, height=height)
    )
