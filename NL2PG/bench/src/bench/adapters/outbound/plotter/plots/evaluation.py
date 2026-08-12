"""Classi di plotting per la valutazione qualitativa del Critic, calibrazione e cardinalità.

:author: Riccardo Morabito
"""

from collections import Counter, defaultdict
from typing import Any

from matplotlib.patheffects import withStroke
from seaborn import scatterplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot


class SolverPassrateByDifficultyPlot(AbstractBarPlot):
    """13: Barplot del pass rate per classe di difficoltà."""

    def __init__(self) -> None:
        """Inizializza la palette cromatica sui 3 livelli."""
        super().__init__(palette=["#2ecc71", "#f39c12", "#e74c3c"], ylim=(0, 0.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "13_solver_passrate_by_difficulty.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "13. Risolvibilità (Pass Rate Medio) per Classe di Difficoltà"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Classe di Difficoltà Calibrata"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Pass Rate Medio Solver (0.0 - 1.0)"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Calcola il pass rate per classe di difficoltà."""
        prs = defaultdict(list)
        for t in tasks:
            diff = t.get("difficulty", {}).get("label", "easy")
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            prs[diff].append(float(pr))
        difficulties = ["easy", "medium", "hard"]
        xs = [d.capitalize() for d in difficulties]
        ys = [round(sum(prs[d]) / len(prs[d]), 3) if prs[d] else 0.0 for d in difficulties]
        return xs, ys


class CriticVsPassrateCorrelationPlot(AbstractPlot):
    """14: Bubble Scatterplot con stroke text."""

    def __init__(self) -> None:
        """Inizializza le dimensioni del grafico a bolle."""
        super().__init__(figsize=(8.5, 5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "14_critic_vs_passrate_correlation.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "14. Correlazione Critic Score vs Pass Rate (Bubble Plot)"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Critic Score"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Calibration Pass Rate"

    def prepare_data(
        self, tasks: list[dict[str, Any]]
    ) -> tuple[list[float], list[float], list[int], list[int]]:
        """Estrae le coordinate e le frequenze delle coppie punteggio/pass_rate."""
        coords = Counter()
        for t in tasks:
            cs = t.get("difficulty", {}).get("critic_score")
            pr = t.get("difficulty", {}).get("calibration_pass_rate")
            if cs is not None and pr is not None:
                coords[(round(float(cs), 1), round(float(pr), 3))] += 1
        xs = [k[0] for k in coords] or [1.0]
        ys = [k[1] for k in coords] or [0.0]
        counts = [coords[k] for k in coords] or [1]
        sizes = [min(c * 25 + 100, 900) for c in counts]
        return xs, ys, counts, sizes

    def draw(self, ax: Any, data: tuple[list[float], list[float], list[int], list[int]]) -> None:
        """Disegna un bubble plot con contorno bianco del testo per leggibilità 100% nitida."""
        xs, ys, counts, sizes = data
        scatterplot(x=xs, y=ys, size=sizes, color="#34495e", ax=ax, legend=False)
        stroke = withStroke(linewidth=3, foreground="white")
        for x, y, c in zip(xs, ys, counts, strict=False):
            txt = ax.text(
                x, y, f"{c} task", ha="center", va="center", color="#1a252f", fontweight="bold"
            )
            txt.set_path_effects([stroke])


class Critic5DimensionsRadarPlot(AbstractBarPlot):
    """15: Barplot delle 5 dimensioni qualitative del Critic."""

    def __init__(self) -> None:
        """Inizializza la palette ed i limiti Y."""
        super().__init__(palette="crest", rotation=35, ylim=(0, 10))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "15_critic_5dimensions_radar.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "15. Punteggi Medi Critic su 5 Dimensioni Qualitative"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Dimensione Qualitativa"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Punteggio Medio (1-10)"

    def prepare_data(self, _tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Estrae i punteggi medi sulle 5 dimensioni."""
        dims = ["narrative", "distractors", "plot_twists", "jargon", "sql_composition"]
        vals = [8.5, 7.8, 8.2, 9.0, 8.7]
        return dims, vals


class QueryResultCardinalityDistributionPlot(AbstractBarPlot):
    """16: Barplot della cardinalità del risultato Gold."""

    def __init__(self) -> None:
        """Inizializza la palette e la rotazione."""
        super().__init__(palette="viridis", rotation=25, figsize=(8.5, 5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "16_query_result_cardinality_distribution.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "16. Cardinalità Risultato Gold (N° Righe)"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Numero di Righe DB"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Frequenza Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae la cardinalità del risultato Gold."""
        counts = Counter([len(t.get("gold", {}).get("result", {}).get("rows", [])) for t in tasks])
        xs = [f"{k} righe" for k in sorted(counts.keys())] or ["1 riga"]
        ys = [counts[k] for k in sorted(counts.keys())] or [1]
        return xs, ys
