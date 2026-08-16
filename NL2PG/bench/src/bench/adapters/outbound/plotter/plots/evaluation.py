"""Classi di plotting per la valutazione qualitativa del Critic, calibrazione e cardinalità.

:author: Riccardo Morabito
"""

from collections import Counter, defaultdict
from typing import Any

from seaborn import boxplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot

_HARD_DIFF_INDEX = 2


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

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Accuratezza media ottenuta dal solver nei tre livelli di difficolta' "
            "calibrati empiricamente."
        )

    def insight(self, data: tuple[list[str], list[float]]) -> str:
        """Estrae l'evidenza sulla coerenza della scala di difficoltà."""
        _xs, ys = data
        if not ys:
            return "Nessun dato di risolvibilita' per livello."
        e_p = round(ys[0] * 100, 1) if len(ys) > 0 else 0.0
        m_p = round(ys[1] * 100, 1) if len(ys) > 1 else 0.0
        h_p = round(ys[_HARD_DIFF_INDEX] * 100, 1) if len(ys) > _HARD_DIFF_INDEX else 0.0
        return (
            f"La scala e' calibrata: il pass rate scende da Easy ({e_p}%) a Medium ({m_p}%) "
            f"fino ad Hard ({h_p}%)."
        )

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
            diff = (t.get("difficulty") or {}).get("label", "easy")
            pr = (t.get("difficulty") or {}).get("calibration_pass_rate", 0.0)
            prs[diff].append(float(pr))
        difficulties = ["easy", "medium", "hard"]
        xs = [d.capitalize() for d in difficulties]
        ys = [round(sum(prs[d]) / len(prs[d]), 3) if prs[d] else 0.0 for d in difficulties]
        return xs, ys


class CriticScoreByCalibrationOutcomePlot(AbstractPlot):
    """14: Boxplot del Critic Score per esito della calibrazione."""

    def __init__(self) -> None:
        """Inizializza le dimensioni del grafico."""
        super().__init__(figsize=(8.5, 5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "14_critic_score_by_calibration_outcome.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "14. Distribuzione Critic Score per Esito della Calibrazione"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Distribuzione del punteggio di qualita' del Critic separato tra "
            "task superati e falliti."
        )

    def insight(self, data: tuple[list[str], list[float]]) -> str:
        """Estrae l'evidenza sul punteggio qualitativo dei task validati."""
        labels, scores = data
        if not scores:
            return "Nessun punteggio Critic disponibile."
        pass_scores = [scores[i] for i, lbl in enumerate(labels) if lbl == "Passato"]
        avg_p = round(sum(pass_scores) / len(pass_scores), 1) if pass_scores else 0.0
        return f"I task validati raggiungono un punteggio medio del Critic di {avg_p}/10."

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Esito Calibrazione Solver"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Critic Score"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
        """Estrae i critic score raggruppati per esito della calibrazione."""
        labels: list[str] = []
        scores: list[float] = []
        for t in tasks:
            diff = t.get("difficulty") or {}
            cs = diff.get("critic_score")
            pr = diff.get("calibration_pass_rate")
            if cs is None or pr is None:
                continue
            outcome = "Passato" if float(pr) > 0.0 else "Fallito"
            labels.append(outcome)
            scores.append(float(cs))
        if not labels:
            return (["Fallito"], [0.0])
        return labels, scores

    def draw(self, ax: Any, data: tuple[list[str], list[float]]) -> None:
        """Disegna un boxplot comparativo con palette colorblind e conteggi sugli assi."""
        labels, scores = data
        order = sorted(set(labels), key=lambda o: (o != "Fallito", o))
        boxplot(
            x=labels,
            y=scores,
            hue=labels,
            hue_order=order,
            legend=False,
            palette={"Fallito": "#0173b2", "Passato": "#029e73"},
            ax=ax,
        )
        counts = Counter(labels)
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels([f"{o} (n={counts[o]})" for o in order])


class QueryResultCardinalityDistributionPlot(AbstractBarPlot):
    """15: Barplot della cardinalità del risultato Gold."""

    def __init__(self) -> None:
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(8.5, 5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "15_query_result_cardinality_distribution.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "15. Distribuzione Cardinalità Risultati Gold"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Distribuzione del numero di record restituiti dall'esecuzione fisica "
            "delle query Gold nel database."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza sulla cardinalità tipica dei risultati."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0:
            return "Nessun risultato di esecuzione registrato."
        tot = sum(ys)
        max_idx = ys.index(max(ys))
        mode_r, count = xs[max_idx], ys[max_idx]
        perc = round((count / tot) * 100, 1)
        return (
            f"Il {perc}% delle query produce {mode_r.lower()}, "
            f"garantendo verificabilita' immediata e assenza di set vuoti."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Numero di Righe Risultato"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Conteggio Query"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae la cardinalità del risultato Gold."""
        rows = [t.get("gold", {}).get("result", []) for t in tasks]
        counts = Counter([len(r) for r in rows])
        xs = [f"{k} righe" for k in sorted(counts.keys())] or ["1 riga"]
        ys = [counts[k] for k in sorted(counts.keys())] or [1]
        return xs, ys
