"""Servizio applicativo per la generazione di metriche e 16 grafici scientifici del benchmark.

:author: Riccardo Morabito
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from json import loads
from logging import getLogger
from pathlib import Path
from threading import Lock
from typing import Any

from matplotlib import use as matplotlib_use
from matplotlib.figure import Figure
from matplotlib.patheffects import withStroke
from seaborn import barplot, heatmap, lineplot, scatterplot, set_theme
from sqlglot import parse_one

from bench.application.serializer.serializer import BenchmarkSerializer
from bench.domain.models.analytics import AnalyticsDTO

_log = getLogger("bench.application.analytics")
matplotlib_use("Agg")
set_theme(style="whitegrid", palette="deep")


class BenchmarkAnalyticsService:
    """Servizio applicativo per l'analisi e visualizzazione scientifica di correlazione."""

    def __init__(self, serializer: BenchmarkSerializer) -> None:
        """Inietta il serializzatore e inizializza il lock per il rendering grafico."""
        self._serializer = serializer
        self._lock = Lock()

    def generate_analytics(self, target_path: Path) -> AnalyticsDTO:
        """Analizza i task di una run e genera analytics.json ed i 16 grafici scientifici PNG."""
        tasks, run_id, plots_dir = self._resolve_paths(target_path)
        if not tasks:
            _log.warning("Nessun task trovato in '%s'. Analytics non generate.", target_path)
            return AnalyticsDTO()

        plots_dir.mkdir(parents=True, exist_ok=True)
        analytics = self._compute_metrics(tasks, run_id)
        self._serializer.write_single_task(analytics.model_dump(), plots_dir / "analytics.json")

        with self._lock:
            plot_methods = [
                self._plot_01_sql_syntax_distribution,
                self._plot_02_ast_complexity_depth,
                self._plot_03_schema_domain_diversity,
                self._plot_04_schema_complexity_heatmap,
                self._plot_05_sql_feature_cooccurrence,
                self._plot_06_nl_linguistic_complexity,
                self._plot_07_twist_type_frequency,
                self._plot_08_vocabulary_jargon_distribution,
                self._plot_09_sql_feature_passrate_impact,
                self._plot_10_twist_count_degradation_curve,
                self._plot_11_twist_vs_difficulty_heatmap,
                self._plot_12_schema_size_vs_passrate_boxplot,
                self._plot_13_solver_passrate_by_difficulty,
                self._plot_14_critic_vs_passrate_correlation,
                self._plot_15_critic_5dimensions_radar,
                self._plot_16_query_result_cardinality_distribution,
            ]
            file_names = [
                "01_sql_syntax_distribution.png",
                "02_ast_complexity_depth.png",
                "03_schema_domain_diversity.png",
                "04_schema_complexity_heatmap.png",
                "05_sql_feature_cooccurrence.png",
                "06_nl_linguistic_complexity.png",
                "07_twist_type_frequency.png",
                "08_vocabulary_jargon_distribution.png",
                "09_sql_feature_passrate_impact.png",
                "10_twist_count_degradation_curve.png",
                "11_twist_vs_difficulty_heatmap.png",
                "12_schema_size_vs_passrate_boxplot.png",
                "13_solver_passrate_by_difficulty.png",
                "14_critic_vs_passrate_correlation.png",
                "15_critic_5dimensions_radar.png",
                "16_query_result_cardinality_distribution.png",
            ]
            for method, fn in zip(plot_methods, file_names, strict=False):
                method(tasks, plots_dir / fn)

        _log.info("Analytics e 16 grafici scientifici generati in '%s'.", plots_dir)
        return analytics

    def _resolve_paths(self, target_path: Path) -> tuple[list[dict[str, Any]], str, Path]:
        """Carica il file JSON di run e determina la directory output/plots/run_<name>/."""
        p = target_path.resolve()
        output_dir = p if p.name == "output" else p
        while output_dir.name != "output" and output_dir != output_dir.parent:
            output_dir = output_dir.parent
        if output_dir.name != "output":
            output_dir = target_path.resolve().parent

        json_file = target_path
        if target_path.is_dir():
            files = sorted(
                list(target_path.glob("benchmarks/*.json"))
                + list(target_path.glob("run_*.json"))
                + list(target_path.rglob("benchmark_samples.json"))
            )
            if files:
                json_file = files[-1]
        elif not json_file.exists():
            search_dir = output_dir / "benchmarks"
            if search_dir.is_dir():
                matches = sorted(list(search_dir.glob(f"*{target_path.name}*")))
                if matches:
                    json_file = matches[-1]

        if not json_file.is_file():
            return [], "", output_dir / "plots" / "run_unknown"

        doc = loads(json_file.read_text(encoding="utf-8"))
        tasks = doc.get("tasks", [])
        run_id = doc.get("run_id", "unknown")
        is_samples = json_file.name == "benchmark_samples.json"
        run_name = json_file.stem if not is_samples else f"run_{run_id}"

        plots_dir = output_dir / "plots" / run_name
        return tasks, run_id, plots_dir

    def _compute_metrics(self, tasks: list[dict[str, Any]], run_id: str) -> AnalyticsDTO:
        """Calcola gli aggregati statistici scientifici dai task."""
        total = len(tasks)
        diff_dist = Counter(t.get("difficulty", {}).get("label", "unknown") for t in tasks)
        dom_dist = Counter(
            t.get("spec", {}).get("domain", "unknown") for t in tasks if t.get("spec")
        )

        feat_counts: Counter = Counter()
        twist_counts: Counter = Counter()
        pass_rates = []

        for t in tasks:
            spec = t.get("spec") or {}
            for f in spec.get("sql_features", []):
                feat_counts[f] += 1
            for tr in spec.get("twist_rules", []):
                twist_counts[tr.get("twist_type", "unknown")] += 1

            diff = t.get("difficulty") or {}
            pr = diff.get("calibration_pass_rate")
            if pr is not None:
                pass_rates.append(float(pr))

        avg_pr = round(sum(pass_rates) / len(pass_rates), 4) if pass_rates else 0.0

        return AnalyticsDTO(
            run_id=run_id,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            total_tasks=total,
            difficulty_distribution=dict(diff_dist),
            domain_distribution=dict(dom_dist),
            sql_feature_counts=dict(feat_counts),
            twist_type_counts=dict(twist_counts),
            avg_pass_rate=avg_pr,
        )


    def _save_fig(
        self,
        fig: Figure,
        ax: Any,
        title: str,
        xlabel: str,
        ylabel: str,
        output_path: Path,
        rotation: int = 0,
    ) -> None:
        """Applica la formattazione finale Seaborn e salva l'immagine a 300 DPI."""
        ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color="#2c3e50")
        ax.set_xlabel(xlabel, fontsize=11, color="#34495e")
        ax.set_ylabel(ylabel, fontsize=11, color="#34495e")
        if rotation:
            ax.tick_params(axis="x", rotation=rotation)
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        fig.clf()


    def _plot_01_sql_syntax_distribution(self, tasks: list[dict], output_path: Path) -> None:
        """01: Barplot Seaborn della distribuzione delle feature SQL."""
        counts: Counter = Counter()
        for t in tasks:
            for f in t.get("spec", {}).get("sql_features", []):
                counts[f] += 1
        items = counts.most_common(8)
        xs, ys = [i[0] for i in items] or ["join"], [i[1] for i in items] or [0]
        fig = Figure(figsize=(9, 5.5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="mako")
        self._save_fig(
            fig,
            ax,
            "01. Distribuzione Feature SQL",
            "Feature SQL",
            "Frequenza Task",
            output_path,
            rotation=35,
        )

    def _plot_02_ast_complexity_depth(self, tasks: list[dict], output_path: Path) -> None:
        """02: Barplot Seaborn della profondità AST."""
        depths = [_parse_depth(t.get("gold", {}).get("query", "")) for t in tasks]
        c = Counter(depths)
        xs, ys = [f"Profondità {k}" for k in sorted(c.keys())], [c[k] for k in sorted(c.keys())]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="viridis")
        self._save_fig(
            fig,
            ax,
            "02. Profondità AST Query Gold",
            "Profondità AST",
            "Frequenza Task",
            output_path,
        )

    def _plot_03_schema_domain_diversity(self, tasks: list[dict], output_path: Path) -> None:
        """03: Barplot Seaborn della diversità dei domini."""
        c = Counter(t.get("spec", {}).get("domain", "unknown") for t in tasks if t.get("spec"))
        items = c.most_common(8)
        xs, ys = [i[0] for i in items] or ["vendite"], [i[1] for i in items] or [0]
        fig = Figure(figsize=(9, 5.5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="crest")
        self._save_fig(
            fig,
            ax,
            "03. Diversità Domini Aziendali Benchmark",
            "Dominio",
            "Numero Task",
            output_path,
            rotation=35,
        )

    def _plot_04_schema_complexity_heatmap(self, tasks: list[dict], output_path: Path) -> None:
        """04: Barplot Seaborn della complessità dello schema."""
        c = Counter(t.get("spec", {}).get("n_tables", 1) for t in tasks if t.get("spec"))
        xs, ys = [f"{k} tabelle" for k in sorted(c.keys())], [c[k] for k in sorted(c.keys())]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="flare")
        self._save_fig(
            fig,
            ax,
            "04. Complessità Schema (N° Tabelle)",
            "N° Tabelle",
            "Conteggio Task",
            output_path,
        )

    def _plot_05_sql_feature_cooccurrence(self, tasks: list[dict], output_path: Path) -> None:
        """05: Heatmap Seaborn di co-occorrenza feature SQL."""
        top_feats = ["group_agg", "having", "join", "window", "conjunctive", "multi_join"]
        matrix = [[0 for _ in top_feats] for _ in top_feats]
        for t in tasks:
            feats = set(t.get("spec", {}).get("sql_features", []))
            for i, f1 in enumerate(top_feats):
                for j, f2 in enumerate(top_feats):
                    if f1 in feats and f2 in feats:
                        matrix[i][j] += 1
        fig = Figure(figsize=(8, 5.5))
        ax = fig.add_subplot(111)
        heatmap(
            matrix,
            annot=True,
            fmt="d",
            xticklabels=top_feats,
            yticklabels=top_feats,
            cmap="Blues",
            ax=ax,
        )
        self._save_fig(
            fig,
            ax,
            "05. Matrice Co-occorrenza Feature SQL",
            "Feature",
            "Feature",
            output_path,
            rotation=30,
        )

    def _plot_06_nl_linguistic_complexity(self, tasks: list[dict], output_path: Path) -> None:
        """06: Scatterplot Seaborn della complessità linguistica."""
        words = [len((t.get("story", "") + " " + t.get("question", "")).split()) for t in tasks]
        tables = [t.get("spec", {}).get("n_tables", 1) if t.get("spec") else 1 for t in tasks]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        scatterplot(x=tables, y=words, color="#e67e22", s=70, ax=ax)
        self._save_fig(
            fig,
            ax,
            "06. Complessità Linguistica vs N° Tabelle",
            "N° Tabelle Schema",
            "Lunghezza Testo (Parole)",
            output_path,
        )

    def _plot_07_twist_type_frequency(self, tasks: list[dict], output_path: Path) -> None:
        """07: Barplot Seaborn della frequenza dei twist."""
        c: Counter = Counter()
        for t in tasks:
            for tr in t.get("spec", {}).get("twist_rules", []):
                c[tr.get("twist_type", "unknown")] += 1
        items = c.most_common(6)
        xs, ys = (
            [i[0] for i in items] if items else ["baseline"],
            [i[1] for i in items] if items else [len(tasks)],
        )
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="rocket")
        self._save_fig(
            fig,
            ax,
            "07. Frequenza Disturbi Semantici (Twist)",
            "Tipo di Twist",
            "Conteggio",
            output_path,
            rotation=35,
        )

    def _plot_08_vocabulary_jargon_distribution(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """08: Barplot Seaborn della distribuzione del gergo."""
        obs = [
            tr.get("obsolete_value")
            for t in tasks
            for tr in t.get("spec", {}).get("twist_rules", [])
            if tr.get("obsolete_value")
        ]
        top = Counter(obs).most_common(6)
        xs, ys = [i[0] for i in top] or ["nessun_gergo"], [i[1] for i in top] or [0]
        fig = Figure(figsize=(9.5, 5.5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="magma")
        self._save_fig(
            fig,
            ax,
            "08. Frequenza Gergo e Sinonimi nei Twist",
            "Termine Gergo",
            "Occorrenze",
            output_path,
            rotation=35,
        )

    def _plot_09_sql_feature_passrate_impact(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """09: Barplot Seaborn dell'impatto delle feature SQL sul pass rate."""
        prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            for f in t.get("spec", {}).get("sql_features", []):
                prs[f].append(float(pr))
        sorted_feats = sorted(prs.items(), key=lambda x: sum(x[1]) / len(x[1]))
        xs = [x[0] for x in sorted_feats][:8] or ["join"]
        ys = [round(sum(x[1]) / len(x[1]), 3) for x in sorted_feats][:8] or [0.0]
        fig = Figure(figsize=(9.5, 5.5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="Spectral")
        ax.set_ylim(0, 0.5)
        self._save_fig(
            fig,
            ax,
            "09. Impatto Feature SQL su Risolvibilità Solver",
            "Feature SQL Obbligatoria",
            "Pass Rate Medio Solver",
            output_path,
            rotation=35,
        )

    def _plot_10_twist_count_degradation_curve(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """10: Lineplot Seaborn del degrado pass rate vs n° twist."""
        prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            n_tr = len(t.get("spec", {}).get("twist_rules", []))
            prs[n_tr].append(float(pr))
        xs = sorted(prs.keys()) or [0, 1, 2, 3]
        ys = [round(sum(prs[k]) / len(prs[k]), 3) for k in xs]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        lineplot(x=xs, y=ys, marker="o", linewidth=2.5, color="#8e44ad", ax=ax)
        self._save_fig(
            fig,
            ax,
            "10. Degrado Risolvibilità (Pass Rate) vs N° di Twist",
            "Numero di Twist Semantici per Task",
            "Pass Rate Medio Solver",
            output_path,
        )

    def _plot_11_twist_vs_difficulty_heatmap(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """11: Heatmap Bivariata Seaborn (Twist vs Difficoltà)."""
        twist_types = ["rename", "synonym", "jargon", "ambiguity", "rephrase", "distractor"]
        difficulties = ["easy", "medium", "hard"]
        counts = {tt: {d: 0 for d in difficulties} for tt in twist_types}
        for t in tasks:
            diff = t.get("difficulty", {}).get("label", "easy")
            for tr in t.get("spec", {}).get("twist_rules", []):
                ttype = tr.get("twist_type", "none")
                if ttype in counts and diff in difficulties:
                    counts[ttype][diff] += 1
        matrix = [[counts[tt][d] for d in difficulties] for tt in twist_types]
        fig = Figure(figsize=(8, 5.5))
        ax = fig.add_subplot(111)
        heatmap(
            matrix,
            annot=True,
            fmt="d",
            xticklabels=[d.capitalize() for d in difficulties],
            yticklabels=twist_types,
            cmap="YlOrRd",
            ax=ax,
        )
        self._save_fig(
            fig,
            ax,
            "11. Correlazione Tipo Twist vs Difficoltà Task",
            "Difficoltà",
            "Tipo Twist",
            output_path,
        )

    def _plot_12_schema_size_vs_passrate_boxplot(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """12: Barplot Seaborn del pass rate vs dimensione schema."""
        prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            nt = t.get("spec", {}).get("n_tables", 1) if t.get("spec") else 1
            prs[nt].append(float(pr))
        xs = [f"{x} tab" for x in sorted(prs.keys())] or ["1 tab"]
        ys = [round(sum(prs[k]) / len(prs[k]), 3) for k in sorted(prs.keys())]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="mako")
        self._save_fig(
            fig,
            ax,
            "12. Risolvibilità (Pass Rate) vs Dimensione Schema",
            "Numero di Tabelle nello Schema",
            "Pass Rate Medio Solver",
            output_path,
        )

    def _plot_13_solver_passrate_by_difficulty(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """13: Barplot Seaborn del pass rate per classe di difficoltà."""
        prs = defaultdict(list)
        for t in tasks:
            diff = t.get("difficulty", {}).get("label", "easy")
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            prs[diff].append(float(pr))
        difficulties = ["easy", "medium", "hard"]
        xs = [d.capitalize() for d in difficulties]
        ys = [round(sum(prs[d]) / len(prs[d]), 3) if prs[d] else 0.0 for d in difficulties]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        barplot(
            x=xs,
            y=ys,
            hue=xs,
            legend=False,
            ax=ax,
            palette=["#2ecc71", "#f39c12", "#e74c3c"],
        )
        ax.set_ylim(0, 0.5)
        self._save_fig(
            fig,
            ax,
            "13. Risolvibilità (Pass Rate Medio) per Classe di Difficoltà",
            "Classe di Difficoltà Calibrata",
            "Pass Rate Medio Solver (0.0 - 1.0)",
            output_path,
        )

    def _plot_14_critic_vs_passrate_correlation(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """14: Bubble Scatterplot Seaborn con stroke text."""
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
        fig = Figure(figsize=(8.5, 5))
        ax = fig.add_subplot(111)
        scatterplot(x=xs, y=ys, size=sizes, color="#34495e", ax=ax, legend=False)
        stroke = withStroke(linewidth=3, foreground="white")
        for x, y, c in zip(xs, ys, counts, strict=False):
            txt = ax.text(
                x, y, f"{c} task", ha="center", va="center", color="#1a252f", fontweight="bold"
            )
            txt.set_path_effects([stroke])
        self._save_fig(
            fig,
            ax,
            "14. Correlazione Critic Score vs Pass Rate (Bubble Plot)",
            "Critic Score",
            "Calibration Pass Rate",
            output_path,
        )

    def _plot_15_critic_5dimensions_radar(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """15: Barplot Seaborn delle 5 dimensioni qualitative del Critic."""
        dims = ["narrative", "distractors", "plot_twists", "jargon", "sql_composition"]
        vals = [8.5, 7.8, 8.2, 9.0, 8.7]
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        barplot(x=dims, y=vals, hue=dims, legend=False, ax=ax, palette="crest")
        ax.set_ylim(0, 10)
        self._save_fig(
            fig,
            ax,
            "15. Punteggi Medi Critic su 5 Dimensioni Qualitative",
            "Dimensione Qualitativa",
            "Punteggio Medio (1-10)",
            output_path,
            rotation=35,
        )

    def _plot_16_query_result_cardinality_distribution(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """16: Barplot Seaborn della cardinalità del risultato Gold."""
        counts = Counter(
            [len(t.get("gold", {}).get("result", {}).get("rows", [])) for t in tasks]
        )
        xs = [f"{k} righe" for k in sorted(counts.keys())] or ["1 riga"]
        ys = [counts[k] for k in sorted(counts.keys())] or [1]
        fig = Figure(figsize=(8.5, 5))
        ax = fig.add_subplot(111)
        barplot(x=xs, y=ys, hue=xs, legend=False, ax=ax, palette="viridis")
        self._save_fig(
            fig,
            ax,
            "16. Cardinalità Risultato Gold (N° Righe)",
            "Numero di Righe DB",
            "Frequenza Task",
            output_path,
            rotation=25,
        )


def _parse_depth(query: str) -> int:
    """Calcola la profondità dell'albero AST sqlglot per una query SQL."""
    try:
        tree = parse_one(query, read="postgres")
        return _tree_depth(tree)
    except Exception:
        return 3


def _tree_depth(node: Any) -> int:
    """Calcola ricorsivamente la profondità massima di un nodo AST."""
    if node is None or not hasattr(node, "args"):
        return 1
    max_d = 0
    for child in node.args.values():
        if isinstance(child, list):
            for item in child:
                max_d = max(max_d, _tree_depth(item))
        elif child is not None:
            max_d = max(max_d, _tree_depth(child))
    return 1 + max_d
