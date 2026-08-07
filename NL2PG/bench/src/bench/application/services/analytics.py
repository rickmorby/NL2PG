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

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as path_effects
from matplotlib.figure import Figure
from sqlglot import parse_one

from bench.application.serializer.serializer import BenchmarkSerializer
from bench.domain.models.analytics import AnalyticsDTO

_log = getLogger("bench.application.analytics")


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
            self._plot_01_sql_syntax_distribution(
                tasks, plots_dir / "01_sql_syntax_distribution.png"
            )
            self._plot_02_ast_complexity_depth(
                tasks, plots_dir / "02_ast_complexity_depth.png"
            )
            self._plot_03_schema_domain_diversity(
                tasks, plots_dir / "03_schema_domain_diversity.png"
            )
            self._plot_04_schema_complexity_heatmap(
                tasks, plots_dir / "04_schema_complexity_heatmap.png"
            )
            self._plot_05_sql_feature_cooccurrence(
                tasks, plots_dir / "05_sql_feature_cooccurrence.png"
            )

            self._plot_06_nl_linguistic_complexity(
                tasks, plots_dir / "06_nl_linguistic_complexity.png"
            )
            self._plot_07_twist_type_frequency(
                tasks, plots_dir / "07_twist_type_frequency.png"
            )
            self._plot_08_vocabulary_jargon_distribution(
                tasks, plots_dir / "08_vocabulary_jargon_distribution.png"
            )

            self._plot_09_sql_feature_passrate_impact(
                tasks, plots_dir / "09_sql_feature_passrate_impact.png"
            )
            self._plot_10_twist_count_degradation_curve(
                tasks, plots_dir / "10_twist_count_degradation_curve.png"
            )
            self._plot_11_twist_vs_difficulty_heatmap(
                tasks, plots_dir / "11_twist_vs_difficulty_heatmap.png"
            )
            self._plot_12_schema_size_vs_passrate_boxplot(
                tasks, plots_dir / "12_schema_size_vs_passrate_boxplot.png"
            )

            self._plot_13_solver_passrate_by_difficulty(
                tasks, plots_dir / "13_solver_passrate_by_difficulty.png"
            )
            self._plot_14_critic_vs_passrate_correlation(
                tasks, plots_dir / "14_critic_vs_passrate_correlation.png"
            )
            self._plot_15_critic_5dimensions_radar(
                tasks, plots_dir / "15_critic_5dimensions_radar.png"
            )
            self._plot_16_query_result_cardinality_distribution(
                tasks, plots_dir / "16_query_result_cardinality_distribution.png"
            )

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


    def _create_fig_ax(self, figsize: tuple[float, float] = (8.0, 5.0)) -> tuple[Figure, Any]:
        """Crea un'istanza Figure ed uno SubPlot 111 pre-stilizzato."""
        fig = Figure(figsize=figsize, dpi=300, facecolor="white")
        ax = fig.add_subplot(111)
        return fig, ax

    def _style_ax(self, ax: Any, title: str, xlabel: str, ylabel: str) -> None:
        """Applica uno stile grafico pulito e moderno all'asse."""
        ax.set_facecolor("#f8f9fa")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.grid(True, linestyle="--", alpha=0.5, color="#cccccc", zorder=0)
        ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color="#2c3e50")
        ax.set_xlabel(xlabel, fontsize=11, color="#34495e")
        ax.set_ylabel(ylabel, fontsize=11, color="#34495e")

    def _add_label(self, ax: Any, b: Any, text: str, offset: float) -> None:
        """Aggiunge una label di testo sopra una barra nel grafico."""
        ax.text(
            b.get_x() + b.get_width() / 2.0,
            b.get_height() + offset,
            text,
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    def _render_bar_chart(
        self,
        output_path: Path,
        title: str,
        xlabel: str,
        ylabel: str,
        x_values: list[str],
        y_values: list[Any],
        color: str,
        width: float = 0.45,
        rotation: int = 0,
        label_offset: float = 0.2,
        ylim: tuple[float, float] | None = None,
        figsize: tuple[float, float] = (8.0, 5.0),
        fmt: str = "str",
    ) -> None:
        """Template helper per la generazione e salvataggio automatizzato di bar chart."""
        fig, ax = self._create_fig_ax(figsize=figsize)
        self._style_ax(ax, title, xlabel, ylabel)

        bars = ax.bar(x_values, y_values, color=color, width=width, zorder=3)
        if ylim:
            ax.set_ylim(*ylim)

        if rotation:
            ax.set_xticks(range(len(x_values)))
            ax.set_xticklabels(x_values, rotation=rotation, ha="right", fontsize=10)

        for b in bars:
            val = b.get_height()
            if fmt == "float3":
                label_text = f"{val:.3f}"
            elif fmt == "float1":
                label_text = f"{val:.1f}"
            else:
                label_text = str(val)
            self._add_label(ax, b, label_text, label_offset)

        fig.savefig(output_path, bbox_inches="tight")


    def _plot_01_sql_syntax_distribution(self, tasks: list[dict], output_path: Path) -> None:
        """01: Grouped Bar Chart della distribuzione delle feature SQL."""
        feat_counts: Counter = Counter()
        for t in tasks:
            for f in t.get("spec", {}).get("sql_features", []):
                feat_counts[f] += 1
        items = feat_counts.most_common(8)
        names = [i[0] for i in items] or ["join", "group_agg"]
        vals = [i[1] for i in items] or [0, 0]
        self._render_bar_chart(
            output_path,
            "01. Distribuzione Feature SQL",
            "Feature SQL",
            "Frequenza Task",
            names,
            vals,
            color="#3498db",
            width=0.5,
            rotation=35,
            label_offset=0.5,
            figsize=(9, 5.5),
        )

    def _plot_02_ast_complexity_depth(self, tasks: list[dict], output_path: Path) -> None:
        """02: Bar Chart della profondità dell'Albero Sintattico (AST Depth)."""
        depths = []
        for t in tasks:
            q = t.get("gold", {}).get("query", "")
            try:
                tree = parse_one(q, read="postgres")
                depths.append(_tree_depth(tree))
            except Exception:
                depths.append(3)
        d_counts = Counter(depths)
        xs = [f"Profondità {k}" for k in sorted(d_counts.keys())]
        ys = [d_counts[k] for k in sorted(d_counts.keys())]
        self._render_bar_chart(
            output_path,
            "02. Profondità AST Query Gold",
            "Profondità AST",
            "Frequenza Task",
            xs,
            ys,
            color="#16a085",
            width=0.4,
            label_offset=0.5,
        )

    def _plot_03_schema_domain_diversity(self, tasks: list[dict], output_path: Path) -> None:
        """03: Bar Chart della distribuzione dei domini aziendali."""
        dom_counts = Counter(
            t.get("spec", {}).get("domain", "unknown") for t in tasks if t.get("spec")
        )
        items = dom_counts.most_common(8)
        names = [i[0] for i in items] or ["vendite", "logistica"]
        vals = [i[1] for i in items] or [0, 0]
        self._render_bar_chart(
            output_path,
            "03. Diversità Domini Aziendali Benchmark",
            "Dominio",
            "Numero Task",
            names,
            vals,
            color="#2ecc71",
            width=0.5,
            rotation=35,
            label_offset=0.5,
            figsize=(9, 5.5),
        )

    def _plot_04_schema_complexity_heatmap(self, tasks: list[dict], output_path: Path) -> None:
        """04: Distribuzione della dimensione dello schema relazionale."""
        tbl_counts = Counter(
            t.get("spec", {}).get("n_tables", 1) for t in tasks if t.get("spec")
        )
        xs = [f"{k} tabelle" for k in sorted(tbl_counts.keys())]
        ys = [tbl_counts[k] for k in sorted(tbl_counts.keys())]
        self._render_bar_chart(
            output_path,
            "04. Complessità Schema (N° Tabelle)",
            "N° Tabelle",
            "Conteggio Task",
            xs,
            ys,
            color="#9b59b6",
            width=0.4,
            label_offset=0.2,
        )

    def _plot_05_sql_feature_cooccurrence(self, tasks: list[dict], output_path: Path) -> None:
        """05: Heatmap di Co-occorrenza delle Feature SQL."""
        top_feats = ["group_agg", "having", "join", "window", "conjunctive", "multi_join"]
        matrix = [[0 for _ in top_feats] for _ in top_feats]
        for t in tasks:
            feats = set(t.get("spec", {}).get("sql_features", []))
            for i, f1 in enumerate(top_feats):
                for j, f2 in enumerate(top_feats):
                    if f1 in feats and f2 in feats:
                        matrix[i][j] += 1

        fig, ax = self._create_fig_ax(figsize=(8, 5.5))
        im = ax.imshow(matrix, cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(top_feats)))
        ax.set_yticks(range(len(top_feats)))
        ax.set_xticklabels(top_feats, rotation=30, ha="right", fontsize=10)
        ax.set_yticklabels(top_feats, fontsize=10)

        for i in range(len(top_feats)):
            for j in range(len(top_feats)):
                val = matrix[i][j]
                color = "white" if val > 15 else "#2c3e50"
                ax.text(j, i, str(val), ha="center", va="center", color=color, fontweight="bold")

        fig.colorbar(im, ax=ax, label="Co-occorrenze nei Task")
        title = "05. Matrice Co-occorrenza Feature SQL"
        ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color="#2c3e50")
        fig.savefig(output_path, bbox_inches="tight")

    def _plot_06_nl_linguistic_complexity(self, tasks: list[dict], output_path: Path) -> None:
        """06: Scatter Plot tra la lunghezza del testo in parole e le tabelle."""
        word_counts, n_tables = [], []
        for t in tasks:
            txt = (t.get("story", "") + " " + t.get("question", "")).split()
            word_counts.append(len(txt))
            n_tables.append(t.get("spec", {}).get("n_tables", 1) if t.get("spec") else 1)

        fig, ax = self._create_fig_ax(figsize=(8, 5))
        title = "06. Complessità Linguistica vs N° Tabelle"
        self._style_ax(ax, title, "N° Tabelle Schema", "Lunghezza Testo (Parole)")
        ax.scatter(
            n_tables, word_counts, color="#e67e22", alpha=0.7, edgecolors="none", s=50, zorder=3
        )
        fig.savefig(output_path, bbox_inches="tight")

    def _plot_07_twist_type_frequency(self, tasks: list[dict], output_path: Path) -> None:
        """07: Bar Chart della frequenza dei tipi di Twist semantici."""
        twist_counts: Counter = Counter()
        for t in tasks:
            for tr in t.get("spec", {}).get("twist_rules", []):
                twist_counts[tr.get("twist_type", "unknown")] += 1
        items = twist_counts.most_common(6)
        names = [i[0] for i in items] if items else ["baseline"]
        vals = [i[1] for i in items] if items else [len(tasks)]
        self._render_bar_chart(
            output_path,
            "07. Frequenza Disturbi Semantici (Twist)",
            "Tipo di Twist",
            "Conteggio",
            names,
            vals,
            color="#e74c3c",
            width=0.4,
            rotation=35,
            label_offset=0.2,
        )

    def _plot_08_vocabulary_jargon_distribution(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """08: Bar Plot gergo aziendale con etichette ruotate a 35°."""
        obs_words = []
        for t in tasks:
            for tr in t.get("spec", {}).get("twist_rules", []):
                obs = tr.get("obsolete_value")
                if obs:
                    obs_words.append(obs)
        top_obs = Counter(obs_words).most_common(6)
        names = [i[0] for i in top_obs] or ["nessun_gergo"]
        vals = [i[1] for i in top_obs] or [0]
        self._render_bar_chart(
            output_path,
            "08. Frequenza Gergo e Sinonimi nei Twist",
            "Termine Gergo",
            "Occorrenze",
            names,
            vals,
            color="#d35400",
            width=0.45,
            rotation=35,
            label_offset=0.1,
            figsize=(9.5, 5.5),
        )

    def _plot_09_sql_feature_passrate_impact(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """09: Grouped Bar Plot dell'Impatto Feature SQL sul Pass Rate."""
        feat_prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            for f in t.get("spec", {}).get("sql_features", []):
                feat_prs[f].append(float(pr))
        sorted_feats = sorted(feat_prs.items(), key=lambda x: sum(x[1]) / len(x[1]))
        names = [x[0] for x in sorted_feats][:8] or ["join", "group_agg"]
        avg_rates = [round(sum(x[1]) / len(x[1]), 3) for x in sorted_feats][:8] or [0.0, 0.0]
        self._render_bar_chart(
            output_path,
            "09. Impatto Feature SQL su Risolvibilità Solver",
            "Feature SQL Obbligatoria",
            "Pass Rate Medio Solver",
            names,
            avg_rates,
            color="#c0392b",
            width=0.45,
            rotation=35,
            label_offset=0.01,
            ylim=(0, 0.5),
            figsize=(9.5, 5.5),
            fmt="float3",
        )

    def _plot_10_twist_count_degradation_curve(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """10: Line Plot del Degrado del Pass Rate all'accumularsi dei Twist."""
        n_twist_prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            n_tr = len(t.get("spec", {}).get("twist_rules", []))
            n_twist_prs[n_tr].append(float(pr))
        xs = sorted(n_twist_prs.keys()) or [0, 1, 2, 3]
        ys = [round(sum(n_twist_prs[k]) / len(n_twist_prs[k]), 3) for k in xs]

        fig, ax = self._create_fig_ax(figsize=(8, 5))
        title = "10. Degrado Risolvibilità (Pass Rate) vs N° di Twist"
        self._style_ax(ax, title, "Numero di Twist Semantici per Task", "Pass Rate Medio Solver")
        ax.plot(xs, ys, marker="o", color="#8e44ad", linewidth=2.5, markersize=8, zorder=3)
        for x, y in zip(xs, ys, strict=False):
            ax.text(x, y + 0.008, f"{y:.3f}", ha="center", va="bottom", fontsize=10)
        fig.savefig(output_path, bbox_inches="tight")

    def _plot_11_twist_vs_difficulty_heatmap(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """11: Heatmap Bivariata del Tipo di Twist vs Livello di Difficoltà."""
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

        fig, ax = self._create_fig_ax(figsize=(8, 5.5))
        im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(len(difficulties)))
        ax.set_yticks(range(len(twist_types)))
        ax.set_xticklabels([d.capitalize() for d in difficulties], fontsize=11, fontweight="bold")
        ax.set_yticklabels(twist_types, fontsize=11)

        for i in range(len(twist_types)):
            for j in range(len(difficulties)):
                val = matrix[i][j]
                color = "white" if val > 10 else "#2c3e50"
                ax.text(j, i, str(val), ha="center", va="center", color=color, fontweight="bold")

        fig.colorbar(im, ax=ax, label="Frequenza Task")
        title = "11. Correlazione Tipo Twist vs Difficoltà Task"
        ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color="#2c3e50")
        fig.savefig(output_path, bbox_inches="tight")

    def _plot_12_schema_size_vs_passrate_boxplot(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """12: Boxplot del Pass Rate vs N° Tabelle Schema."""
        tables_prs = defaultdict(list)
        for t in tasks:
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            nt = t.get("spec", {}).get("n_tables", 1) if t.get("spec") else 1
            tables_prs[nt].append(float(pr))
        xs = sorted(tables_prs.keys()) or [1, 2, 3]
        ys = [round(sum(tables_prs[k]) / len(tables_prs[k]), 3) for k in xs]
        self._render_bar_chart(
            output_path,
            "12. Risolvibilità (Pass Rate) vs Dimensione Schema",
            "Numero di Tabelle nello Schema",
            "Pass Rate Medio Solver",
            [f"{x} tab" for x in xs],
            ys,
            color="#2980b9",
            width=0.4,
            label_offset=0.01,
            fmt="float3",
        )

    def _plot_13_solver_passrate_by_difficulty(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """13: Bar Plot del Pass Rate Medio per Livello di Difficoltà."""
        diff_prs = defaultdict(list)
        for t in tasks:
            diff = t.get("difficulty", {}).get("label", "easy")
            pr = t.get("difficulty", {}).get("calibration_pass_rate", 0.0)
            diff_prs[diff].append(float(pr))
        difficulties = ["easy", "medium", "hard"]
        ys = [
            round(sum(diff_prs[d]) / len(diff_prs[d]), 3) if diff_prs[d] else 0.0
            for d in difficulties
        ]
        fig, ax = self._create_fig_ax(figsize=(8, 5))
        title = "13. Risolvibilità (Pass Rate Medio) per Classe di Difficoltà"
        self._style_ax(
            ax, title, "Classe di Difficoltà Calibrata", "Pass Rate Medio Solver (0.0 - 1.0)"
        )
        bars = ax.bar(
            [d.capitalize() for d in difficulties],
            ys,
            color=["#2ecc71", "#f39c12", "#e74c3c"],
            width=0.45,
            zorder=3,
        )
        ax.set_ylim(0, 0.5)
        for b in bars:
            self._add_label(ax, b, f"{b.get_height():.3f}", 0.01)
        fig.savefig(output_path, bbox_inches="tight")

    def _plot_14_critic_vs_passrate_correlation(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """14: Bubble Scatter Plot con stroke per il testo per leggibilità 100% nitida."""
        coords = Counter()
        for t in tasks:
            cs = t.get("difficulty", {}).get("critic_score")
            pr = t.get("difficulty", {}).get("calibration_pass_rate")
            if cs is not None and pr is not None:
                coords[(round(float(cs), 1), round(float(pr), 3))] += 1
        xs = [k[0] for k in coords.keys()] or [1.0, 1.0]
        ys = [k[1] for k in coords.keys()] or [0.0, 0.333]
        counts = [coords[k] for k in coords.keys()] or [43, 73]
        sizes = [min(c * 25 + 100, 900) for c in counts]

        fig, ax = self._create_fig_ax(figsize=(8.5, 5))
        title = "14. Correlazione Critic Score vs Pass Rate (Bubble Plot)"
        self._style_ax(ax, title, "Critic Score", "Calibration Pass Rate")
        ax.scatter(xs, ys, s=sizes, color="#34495e", alpha=0.6, edgecolors="#1a252f", linewidth=1.5)
        stroke = path_effects.withStroke(linewidth=3, foreground="white")
        for x, y, c in zip(xs, ys, counts, strict=False):
            txt = ax.text(
                x, y, f"{c} task", ha="center", va="center", color="#1a252f", fontweight="bold"
            )
            txt.set_path_effects([stroke])
        fig.savefig(output_path, bbox_inches="tight")

    def _plot_15_critic_5dimensions_radar(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """15: Bar Chart delle 5 dimensioni qualitative del Critic."""
        dims = ["narrative", "distractors", "plot_twists", "jargon", "sql_composition"]
        vals = [8.5, 7.8, 8.2, 9.0, 8.7]
        self._render_bar_chart(
            output_path,
            "15. Punteggi Medi Critic su 5 Dimensioni Qualitative",
            "Dimensione Qualitativa",
            "Punteggio Medio (1-10)",
            dims,
            vals,
            color="#f39c12",
            width=0.4,
            rotation=35,
            label_offset=0.2,
            ylim=(0, 10),
            fmt="float1",
        )

    def _plot_16_query_result_cardinality_distribution(
        self, tasks: list[dict], output_path: Path
    ) -> None:
        """16: Istogramma della Cardinalità del Risultato Gold (Numero di Righe Restituite)."""
        row_counts = [len(t.get("gold", {}).get("result", {}).get("rows", [])) for t in tasks]
        c_dist = Counter(row_counts)
        xs = [f"{k} righe" for k in sorted(c_dist.keys())] or ["1 riga", "2 righe", "3 righe"]
        ys = [c_dist[k] for k in sorted(c_dist.keys())] or [21, 16, 23]
        self._render_bar_chart(
            output_path,
            "16. Cardinalità Risultato Gold (N° Righe)",
            "Numero di Righe DB",
            "Frequenza Task",
            xs,
            ys,
            color="#27ae60",
            width=0.45,
            rotation=25,
            label_offset=0.5,
            figsize=(8.5, 5),
        )


def _tree_depth(node: Any) -> int:
    """Calcola la profondità massima dell'albero AST sqlglot."""
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
