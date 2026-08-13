"""Classi di plotting per la risolvibilità ed i pass rate.

:author: Riccardo Morabito
"""

from collections import defaultdict
from typing import Any

from seaborn import lineplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot
from bench.adapters.outbound.plotter.heatmap_plot import AbstractHeatmapPlot


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
    """10: Lineplot del degrado pass rate vs n° twist."""

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "10_twist_count_degradation_curve.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "10. Degrado Risolvibilità (Pass Rate) vs N° di Twist"

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
        return self._twist_types

    def prepare_data(self, tasks: list[dict[str, Any]]) -> list[list[int]]:
        """Calcola la matrice bivariata delle frequenze."""
        counts = {tt: {d: 0 for d in self._difficulties} for tt in self._twist_types}
        for t in tasks:
            diff = (t.get("difficulty") or {}).get("label", "easy")
            for tr in (t.get("spec") or {}).get("twist_rules", []):
                ttype = tr.get("twist_type", "none")
                if ttype in counts and diff in self._difficulties:
                    counts[ttype][diff] += 1
        return [[counts[tt][d] for d in self._difficulties] for tt in self._twist_types]


class SchemaSizeVsPassrateBoxplotPlot(AbstractBarPlot):
    """12: Barplot del pass rate vs dimensione schema."""

    def __init__(self) -> None:
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(8.5, 5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "12_schema_size_vs_passrate_boxplot.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "12. Risolvibilità (Pass Rate) vs Dimensione Schema"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Numero di Tabelle nello Schema"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Pass Rate Medio Solver"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Calcola il pass rate in base alle dimensioni dello schema."""
        prs = defaultdict(list)
        for t in tasks:
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            nt = (t.get("spec") or {}).get("n_tables", 1)
            prs[nt].append(float(pr))
        xs = [f"{x} tab" for x in sorted(prs.keys())] or ["1 tab"]
        ys = [round(sum(prs[k]) / len(prs[k]), 3) for k in sorted(prs.keys())]
        return xs, ys
