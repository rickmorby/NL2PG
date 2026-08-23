"""Classi di plotting per la risolvibilità ed i pass rate.

:author: Riccardo Morabito
"""

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any

from seaborn import lineplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot
from bench.adapters.outbound.plotter.grouped_bar_plot import AbstractGroupedBarPlot

_TABLE_BINS: list[tuple[int, int, str]] = [
    (1, 2, "1-2"),
    (3, 4, "3-4"),
    (5, 6, "5-6"),
    (7, 12, "7-12"),
]


def _bucket_n_tables(n_tables: int) -> str:
    """Raggruppa il numero di tabelle in fasce per campioni statisticamente robusti."""
    for lo, hi, label in _TABLE_BINS:
        if lo <= n_tables <= hi:
            return label
    return "7-12"


class SqlFeaturePassrateImpactPlot(AbstractBarPlot):
    """09: Barplot dell'impatto delle feature SQL sul pass rate."""

    def __init__(self) -> None:
        """Inizializza la rotazione ed i limiti Y."""
        super().__init__(rotation=35, ylim=(0, 1.0), figsize=(9.5, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "09_sql_feature_passrate_impact.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "09. Impatto Feature SQL su Risolvibilità Solver"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Tasso medio di successo (Pass Rate) del solver per ciascun operatore SQL "
            "in calibrazione."
        )

    def insight(self, data: tuple[list[str], list[float]]) -> str:
        """Estrae l'evidenza sul costrutto SQL con minore risolvibilità."""
        xs, ys = data
        if not xs or not ys:
            return "Nessun dato di calibrazione disponibile."
        min_idx = ys.index(min(ys))
        hardest_f, min_pr = xs[min_idx], round(ys[min_idx] * 100, 1)
        return (
            f"L'operatore piu' ostico per il solver e' '{hardest_f}' "
            f"(pass rate medio del {min_pr}%)."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Feature SQL Obbligatoria"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Pass Rate Medio Solver"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Calcola la media del pass rate per ogni feature SQL presente nei task."""
        prs = defaultdict(list)
        for t in tasks:
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            for f in (t.get("spec") or {}).get("sql_features", []):
                prs[f].append(float(pr))
        sorted_feats = sorted(prs.items(), key=lambda x: sum(x[1]) / len(x[1]))
        xs = [x[0] for x in sorted_feats] or ["join"]
        ys = [round(sum(x[1]) / len(x[1]), 3) for x in sorted_feats] or [0.0]
        self._adapt_layout(len(xs))
        return xs, ys


class TwistCountDegradationCurvePlot(AbstractPlot):
    """10: Lineplot del degrado pass rate vs n. twist."""

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "10_twist_count_degradation_curve.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "10. Degrado Risolvibilità (Pass Rate) vs N. di Twist"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Curva di decadimento: come varia il pass rate del solver al crescere "
            "dei disturbi semantici."
        )

    def insight(self, data: tuple[list[int], list[float]]) -> str:
        """Estrae l'evidenza sulla dinamica di accuratezza al crescere dei disturbi."""
        xs, ys = data
        if not xs or not ys:
            return "Nessuna curva di degradazione calcolabile."
        pr_start = round(ys[0] * 100, 1)
        pr_end = round(ys[-1] * 100, 1)
        if pr_end < pr_start:
            delta = round(pr_start - pr_end, 1)
            return (
                f"L'aumento a {xs[-1]} twist riduce il pass rate da {pr_start}% a {pr_end}% "
                f"(calo netto di {delta}%)."
            )
        if pr_end > pr_start:
            delta = round(pr_end - pr_start, 1)
            return (
                f"Il pass rate varia dal {pr_start}% (0 twist) al {pr_end}% ({xs[-1]} twist), "
                f"con una variazione di +{delta}%."
            )
        return f"Il pass rate si mantiene stabile al {pr_start}% all'aumentare dei disturbi."

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Numero di Twist Semantici per Task"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Pass Rate Medio Solver"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[int], list[float]]:
        """Calcola il degrado pass rate in funzione del numero di twist."""
        if not tasks:
            return ([0], [0.0])
        prs = defaultdict(list)
        for t in tasks:
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            n_tr = len((t.get("spec") or {}).get("twist_rules", []))
            prs[n_tr].append(float(pr))
        xs = sorted(prs.keys()) or [0]
        ys = [round(sum(prs[k]) / len(prs[k]), 3) if prs[k] else 0.0 for k in xs]
        return xs, ys

    def draw(self, ax: Any, data: tuple[list[int], list[float]]) -> None:
        """Disegna una curva lineplot."""
        xs, ys = data
        lineplot(x=xs, y=ys, marker="o", linewidth=2.5, color="#8e44ad", ax=ax)


class TwistVsDifficultyPlot(AbstractGroupedBarPlot):
    """11: Barplot raggruppato (Twist vs Difficoltà binaria)."""

    def __init__(self) -> None:
        """Inizializza palette e difficoltà binarie; i twist sono derivati dai task."""
        super().__init__(palette=["#2ecc71", "#e74c3c"], rotation=35)
        self._twist_types: list[str] = []
        self._difficulties = ["easy", "hard"]

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "11_twist_vs_difficulty.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "11. Numero di Task per Tipo Twist e Classe di Difficoltà"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Confronto binario del numero di task per tipologia di disturbo semantico "
            "tra le classi di difficolta' Easy e Hard."
        )

    def insight(self, data: tuple[list[str], dict[str, list[int]]]) -> str:
        """Estrae l'evidenza sul disturbo a maggiore impatto sulla difficoltà Hard."""
        twist_types, by_group = data
        hard = by_group.get("Hard") or []
        if not twist_types or not hard or not any(hard):
            return "Nessuna correlazione calcolabile."
        max_hard_idx = hard.index(max(hard))
        top_twist_hard = twist_types[max_hard_idx]
        return (
            f"I disturbi di tipo '{top_twist_hard}' sono la causa principale "
            f"di difficolta' Hard nel dataset."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Tipo Twist"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Numero di Task"

    def prepare_data(
        self,
        tasks: list[dict[str, Any]],
    ) -> tuple[list[str], dict[str, list[int]]]:
        """Calcola i conteggi per tipo twist e classe di difficoltà (gruppi binari)."""
        type_counts: Counter = Counter()
        for t in tasks:
            for tr in (t.get("spec") or {}).get("twist_rules", []):
                ttype = tr.get("twist_type", "").lower()
                if ttype:
                    type_counts[ttype] += 1
        self._twist_types = [tt for tt, _ in type_counts.most_common()] or ["rename"]
        groups = [d.capitalize() for d in self._difficulties]
        by_group = {g: [0] * len(self._twist_types) for g in groups}
        for t in tasks:
            diff = (t.get("difficulty") or {}).get("label", "easy").lower()
            if diff not in self._difficulties:
                continue
            for tr in (t.get("spec") or {}).get("twist_rules", []):
                ttype = tr.get("twist_type", "").lower()
                if ttype in self._twist_types:
                    by_group[diff.capitalize()][self._twist_types.index(ttype)] += 1
        self._adapt_layout(len(self._twist_types))
        return self._twist_types, by_group


class SchemaSizeVsPassrateBoxplotPlot(AbstractPlot):
    """12: Boxplot dello schema size vs pass rate."""

    def __init__(self) -> None:
        """Inizializza le dimensioni del grafico."""
        super().__init__(figsize=(8.5, 5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "12_schema_size_vs_passrate_boxplot.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "12. Distribuzione Pass Rate per N. Tabelle"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Distribuzione del pass rate del solver per fasce di dimensione dello schema "
            "(numero di tabelle relazionali nel database)."
        )

    def insight(self, data: tuple[list[str], list[float]]) -> str:
        """Estrae l'evidenza sull'impatto della dimensione dello schema."""
        labels, prs = data
        if not prs:
            return "Nessun dato sul pass rate per dimensione schema."
        grouped: dict[str, list[float]] = {}
        for lbl, pr in zip(labels, prs, strict=True):
            grouped.setdefault(lbl, []).append(pr)
        medians = {lbl: median(vals) for lbl, vals in grouped.items()}
        ordered = [lbl for _, _, lbl in _TABLE_BINS if lbl in medians]
        if not ordered:
            return "Nessun dato sul pass rate per dimensione schema."
        first = medians[ordered[0]]
        last = medians[ordered[-1]]
        first_pct = round(first * 100, 1)
        last_pct = round(last * 100, 1)
        if last < first:
            delta = round((first - last) * 100, 1)
            return (
                f"Il pass rate mediano scende dal {first_pct}% (fascia {ordered[0]}) "
                f"al {last_pct}% (fascia {ordered[-1]}): calo di {delta}%."
            )
        if last > first:
            delta = round((last - first) * 100, 1)
            return (
                f"Il pass rate mediano sale dal {first_pct}% (fascia {ordered[0]}) "
                f"al {last_pct}% (fascia {ordered[-1]}): +{delta}%."
            )
        return (
            f"Il pass rate mediano resta stabile al {first_pct}% "
            f"tra la fascia {ordered[0]} e la fascia {ordered[-1]}."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N. Tabelle nello Schema"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Pass Rate Calibrazione Solver"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Estrae il pass rate medio (proporzione di successi) per fascia di tabelle."""
        labels: list[str] = []
        prs: list[float] = []
        for t in tasks:
            n_tab = (t.get("spec") or {}).get("n_tables", 1)
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            labels.append(_bucket_n_tables(n_tab))
            prs.append(float(pr))
        return labels, prs

    def draw(self, ax: Any, data: tuple[list[str], list[float]]) -> None:
        """Disegna un barplot del pass rate percentuale per fascia di tabelle.

        Poiché ``calibration_pass_rate`` è binario (0 o 1), un boxplot non è
        informativo: si usa la media aritmetica come proporzione di successi,
        che è la rappresentazione standard nei paper per outcome dicotomici.
        """
        labels, prs = data
        order = [lbl for _, _, lbl in _TABLE_BINS if lbl in set(labels)]
        grouped: dict[str, list[float]] = {}
        for lbl, pr in zip(labels, prs, strict=True):
            grouped.setdefault(lbl, []).append(pr)
        means = [mean(grouped[lbl]) * 100 if grouped[lbl] else 0 for lbl in order]
        counts = {lbl: len(grouped[lbl]) for lbl in order}
        tick_labels = [f"{lbl}\n(n={counts[lbl]})" for lbl in order]
        ax.bar(range(len(order)), means, color="#2980b9", width=0.6)
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(tick_labels)
        self._max_data_val = max(means, default=1.0)
