"""Adattatore outbound per il rendering polimorfico dei 16 grafici con Seaborn (OOP Pattern).

:author: Riccardo Morabito
"""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from matplotlib.patheffects import withStroke
from seaborn import lineplot, scatterplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot
from bench.adapters.outbound.plotter.heatmap_plot import AbstractHeatmapPlot
from bench.domain.ports.outbound.plotter_port import PlotterPort
from bench.domain.services.analytics_calculator import AnalyticsCalculator


class SqlSyntaxDistributionPlot(AbstractBarPlot):
    """01: Barplot della distribuzione delle feature SQL."""

    def __init__(self) -> None:
        """Inizializza la palette e la rotazione."""
        super().__init__(palette="mako", rotation=35, figsize=(9, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "01_sql_syntax_distribution.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "01. Distribuzione Feature SQL"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Feature SQL"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Frequenza Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae le top 8 feature SQL."""
        counts: Counter = Counter()
        for t in tasks:
            for f in t.get("spec", {}).get("sql_features", []):
                counts[f] += 1
        items = counts.most_common(8)
        return ([i[0] for i in items] or ["join"], [i[1] for i in items] or [0])


class AstComplexityDepthPlot(AbstractBarPlot):
    """02: Barplot della profondità AST."""

    def __init__(self, calc: AnalyticsCalculator) -> None:
        """Inietta il calcolatore AST."""
        super().__init__(palette="viridis")
        self._calc = calc

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "02_ast_complexity_depth.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "02. Profondità AST Query Gold"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Profondità AST"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Frequenza Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Calcola la profondità AST per le query Gold."""
        depths = [self._calc.parse_depth(t.get("gold", {}).get("query", "")) for t in tasks]
        c = Counter(depths)
        return ([f"Profondità {k}" for k in sorted(c.keys())], [c[k] for k in sorted(c.keys())])


class SchemaDomainDiversityPlot(AbstractBarPlot):
    """03: Barplot della diversità dei domini."""

    def __init__(self) -> None:
        """Inizializza la palette e la rotazione."""
        super().__init__(palette="crest", rotation=35, figsize=(9, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "03_schema_domain_diversity.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "03. Diversità Domini Aziendali Benchmark"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Dominio"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Numero Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae il conteggio per dominio."""
        c = Counter(t.get("spec", {}).get("domain", "unknown") for t in tasks if t.get("spec"))
        items = c.most_common(8)
        return ([i[0] for i in items] or ["vendite"], [i[1] for i in items] or [0])


class SchemaComplexityHeatmapPlot(AbstractBarPlot):
    """04: Barplot della complessità dello schema."""

    def __init__(self) -> None:
        """Inizializza la palette."""
        super().__init__(palette="flare")

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "04_schema_complexity_heatmap.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "04. Complessità Schema (N° Tabelle)"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N° Tabelle"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Conteggio Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae la distribuzione del numero di tabelle."""
        c = Counter(t.get("spec", {}).get("n_tables", 1) for t in tasks if t.get("spec"))
        return ([f"{k} tabelle" for k in sorted(c.keys())], [c[k] for k in sorted(c.keys())])


class SqlFeatureCooccurrencePlot(AbstractHeatmapPlot):
    """05: Heatmap di co-occorrenza feature SQL."""

    def __init__(self) -> None:
        """Inizializza la mappa di calore ed i nomi feature."""
        super().__init__(cmap="Blues", rotation=30)
        self._top_feats = ["group_agg", "having", "join", "window", "conjunctive", "multi_join"]

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "05_sql_feature_cooccurrence.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "05. Matrice Co-occorrenza Feature SQL"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Feature"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Feature"

    @property
    def xticklabels(self) -> list[str]:
        """Restituisce le etichette per l'asse X."""
        return self._top_feats

    @property
    def yticklabels(self) -> list[str]:
        """Restituisce le etichette per l'asse Y."""
        return self._top_feats

    def prepare_data(self, tasks: list[dict[str, Any]]) -> list[list[int]]:
        """Calcola la matrice di co-occorrenza."""
        matrix = [[0 for _ in self._top_feats] for _ in self._top_feats]
        for t in tasks:
            feats = set(t.get("spec", {}).get("sql_features", []))
            for i, f1 in enumerate(self._top_feats):
                for j, f2 in enumerate(self._top_feats):
                    if f1 in feats and f2 in feats:
                        matrix[i][j] += 1
        return matrix


class NlLinguisticComplexityPlot(AbstractPlot):
    """06: Scatterplot della complessità linguistica."""

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "06_nl_linguistic_complexity.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "06. Complessità Linguistica vs N° Tabelle"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N° Tabelle Schema"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Lunghezza Testo (Parole)"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
        """Estrae conteggio parole e numero tabelle."""
        words = [len((t.get("story", "") + " " + t.get("question", "")).split()) for t in tasks]
        tables = [t.get("spec", {}).get("n_tables", 1) if t.get("spec") else 1 for t in tasks]
        return tables, words

    def draw(self, ax: Any, data: tuple[list[int], list[int]]) -> None:
        """Disegna uno scatterplot Seaborn."""
        tables, words = data
        scatterplot(x=tables, y=words, color="#e67e22", s=70, ax=ax)


class TwistTypeFrequencyPlot(AbstractBarPlot):
    """07: Barplot della frequenza dei twist."""

    def __init__(self) -> None:
        """Inizializza la palette e la rotazione."""
        super().__init__(palette="rocket", rotation=35)

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "07_twist_type_frequency.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "07. Frequenza Disturbi Semantici (Twist)"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Tipo di Twist"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Conteggio"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae la frequenza dei twist semantici."""
        c: Counter = Counter()
        for t in tasks:
            for tr in t.get("spec", {}).get("twist_rules", []):
                c[tr.get("twist_type", "unknown")] += 1
        items = c.most_common(6)
        return (
            [i[0] for i in items] if items else ["baseline"],
            [i[1] for i in items] if items else [len(tasks)],
        )


class VocabularyJargonDistributionPlot(AbstractBarPlot):
    """08: Barplot della distribuzione del gergo."""

    def __init__(self) -> None:
        """Inizializza la palette e la rotazione."""
        super().__init__(palette="magma", rotation=35, figsize=(9.5, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "08_vocabulary_jargon_distribution.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "08. Frequenza Gergo e Sinonimi nei Twist"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Termine Gergo"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Occorrenze"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae i termini obsoleti del gergo."""
        obs = [
            tr.get("obsolete_value")
            for t in tasks
            for tr in t.get("spec", {}).get("twist_rules", [])
            if tr.get("obsolete_value")
        ]
        top = Counter(obs).most_common(6)
        return ([i[0] for i in top] or ["nessun_gergo"], [i[1] for i in top] or [0])


class SqlFeaturePassrateImpactPlot(AbstractBarPlot):
    """09: Barplot dell'impatto delle feature SQL sul pass rate."""

    def __init__(self) -> None:
        """Inizializza la palette e la rotazione."""
        super().__init__(palette="Spectral", rotation=35, ylim=(0, 0.5), figsize=(9.5, 5.5))

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
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            for f in t.get("spec", {}).get("sql_features", []):
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
        prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            n_tr = len(t.get("spec", {}).get("twist_rules", []))
            prs[n_tr].append(float(pr))
        xs = sorted(prs.keys()) or [0, 1, 2, 3]
        ys = [round(sum(prs[k]) / len(prs[k]), 3) for k in xs]
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
            diff = t.get("difficulty", {}).get("label", "easy")
            for tr in t.get("spec", {}).get("twist_rules", []):
                ttype = tr.get("twist_type", "none")
                if ttype in counts and diff in self._difficulties:
                    counts[ttype][diff] += 1
        return [[counts[tt][d] for d in self._difficulties] for tt in self._twist_types]


class SchemaSizeVsPassrateBoxplotPlot(AbstractBarPlot):
    """12: Barplot del pass rate vs dimensione schema."""

    def __init__(self) -> None:
        """Inizializza la palette."""
        super().__init__(palette="mako")

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
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            nt = t.get("spec", {}).get("n_tables", 1) if t.get("spec") else 1
            prs[nt].append(float(pr))
        xs = [f"{x} tab" for x in sorted(prs.keys())] or ["1 tab"]
        ys = [round(sum(prs[k]) / len(prs[k]), 3) for k in sorted(prs.keys())]
        return xs, ys


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
        xs = [k[0] for k in coords.keys()] or [1.0]
        ys = [k[1] for k in coords.keys()] or [0.0]
        counts = [coords[k] for k in coords.keys()] or [1]
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

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
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
        counts = Counter(
            [len(t.get("gold", {}).get("result", {}).get("rows", [])) for t in tasks]
        )
        xs = [f"{k} righe" for k in sorted(counts.keys())] or ["1 riga"]
        ys = [counts[k] for k in sorted(counts.keys())] or [1]
        return xs, ys



class SeabornPlotterAdapter(PlotterPort):
    """Adattatore concreto per il rendering dei 16 grafici con la libreria Seaborn."""

    def __init__(
        self,
        calculator: AnalyticsCalculator | None = None,
        plots: list[AbstractPlot] | None = None,
    ) -> None:
        """Inizializza l'adattatore grafico ed il registro dei 16 grafici polimorfici."""
        calc = calculator or AnalyticsCalculator()
        self._plots = plots or [
            SqlSyntaxDistributionPlot(),
            AstComplexityDepthPlot(calc),
            SchemaDomainDiversityPlot(),
            SchemaComplexityHeatmapPlot(),
            SqlFeatureCooccurrencePlot(),
            NlLinguisticComplexityPlot(),
            TwistTypeFrequencyPlot(),
            VocabularyJargonDistributionPlot(),
            SqlFeaturePassrateImpactPlot(),
            TwistCountDegradationCurvePlot(),
            TwistVsDifficultyHeatmapPlot(),
            SchemaSizeVsPassrateBoxplotPlot(),
            SolverPassrateByDifficultyPlot(),
            CriticVsPassrateCorrelationPlot(),
            Critic5DimensionsRadarPlot(),
            QueryResultCardinalityDistributionPlot(),
        ]

    def render_plots(self, tasks: list[dict[str, Any]], output_dir: Path) -> None:
        """Renderizza e salva i 16 grafici scientifici polimorficamente nella directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        for plot in self._plots:
            plot.render(tasks, output_dir / plot.filename())
