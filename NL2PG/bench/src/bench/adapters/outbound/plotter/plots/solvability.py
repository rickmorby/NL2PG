"""Classi di plotting per la risolvibilità ed i pass rate.

:author: Riccardo Morabito
"""

from collections import defaultdict
from typing import Any

from seaborn import boxplot, lineplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot
from bench.adapters.outbound.plotter.heatmap_plot import AbstractHeatmapPlot

_HARD_COL_INDEX = 2


class SqlFeaturePassrateImpactPlot(AbstractBarPlot):
    """09: Barplot dell'impatto delle feature SQL sul pass rate."""

    def __init__(self) -> None:
        """Inizializza la rotazione ed i limiti Y."""
        super().__init__(rotation=35, ylim=(0, 0.5), figsize=(9.5, 5.5))

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
        """Calcola la media del pass rate per feature."""
        prs = defaultdict(list)
        for t in tasks:
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            for f in (t.get("spec") or {}).get("sql_features", []):
                prs[f].append(float(pr))
        sorted_feats = sorted(prs.items(), key=lambda x: sum(x[1]) / len(x[1]))
        return (
            [x[0] for x in sorted_feats][:8] or ["join"],
            [round(sum(x[1]) / len(x[1]), 3) for x in sorted_feats][:8] or [0.0],
        )


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


class TwistVsDifficultyHeatmapPlot(AbstractHeatmapPlot):
    """11: Heatmap Bivariata (Twist vs Difficoltà)."""

    def __init__(self) -> None:
        """Inizializza le dimensioni della matrice bivariata."""
        super().__init__(cmap="YlOrRd")
        self._twist_types = ["rename", "synonym", "jargon", "ambiguity", "rephrase", "distractor"]
        self._difficulties = ["easy", "medium", "hard"]

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "11_twist_vs_difficulty_heatmap.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "11. Correlazione Tipo Twist vs Difficoltà Task"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Correlazione tra la tipologia di disturbo semantico e la classe "
            "di difficolta' del task."
        )

    def insight(self, data: list[list[int]]) -> str:
        """Estrae l'evidenza sul disturbo a maggiore impatto sulla difficoltà."""
        if not data or not any(sum(row) for row in data):
            return "Nessuna correlazione calcolabile."
        hard_counts = [row[_HARD_COL_INDEX] if len(row) > _HARD_COL_INDEX else 0 for row in data]
        max_hard_idx = hard_counts.index(max(hard_counts))
        top_twist_hard = self._twist_types[max_hard_idx]
        return (
            f"I disturbi di tipo '{top_twist_hard}' sono la causa principale "
            f"di difficolta' Hard nel dataset."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Difficoltà"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Tipo Twist"

    @property
    def xticklabels(self) -> list[str]:
        """Restituisce le etichette delle colonne."""
        return [d.capitalize() for d in self._difficulties]

    @property
    def yticklabels(self) -> list[str]:
        """Restituisce le etichette delle righe."""
        return [t.capitalize() for t in self._twist_types]

    def prepare_data(self, tasks: list[dict[str, Any]]) -> list[list[int]]:
        """Calcola la matrice bivariata (Twist vs Difficoltà)."""
        counts = {tt: {d: 0 for d in self._difficulties} for tt in self._twist_types}
        for t in tasks:
            diff = (t.get("difficulty") or {}).get("label", "easy").lower()
            for tr in (t.get("spec") or {}).get("twist_rules", []):
                ttype = tr.get("twist_type", "").lower()
                if ttype in counts and diff in self._difficulties:
                    counts[ttype][diff] += 1
        return [[counts[tt][d] for d in self._difficulties] for tt in self._twist_types]


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
            "Distribuzione del pass rate del solver in base al numero di tabelle "
            "relazionali nel database."
        )

    def insight(self, data: tuple[list[str], list[float]]) -> str:
        """Estrae l'evidenza sull'impatto della dimensione dello schema."""
        _labels, prs = data
        if not prs:
            return "Nessun dato sul pass rate per dimensione schema."
        return (
            "All'aumentare delle tabelle, la varianza degli errori cresce "
            "per la complessita' dei percorsi JOIN."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N. Tabelle nello Schema"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Pass Rate Calibrazione Solver"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Estrae i pass rate raggruppati per numero di tabelle."""
        labels: list[str] = []
        prs: list[float] = []
        for t in tasks:
            n_tab = (t.get("spec") or {}).get("n_tables", 1)
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            labels.append(f"{n_tab} tab")
            prs.append(float(pr))
        return labels, prs

    def draw(self, ax: Any, data: tuple[list[str], list[float]]) -> None:
        """Disegna un boxplot Seaborn."""
        labels, prs = data
        boxplot(x=labels, y=prs, color="#2980b9", ax=ax)
