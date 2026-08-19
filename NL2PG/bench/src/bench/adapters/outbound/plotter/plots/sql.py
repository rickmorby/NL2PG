"""Classi di plotting per la sintassi SQL e la struttura del database.

:author: Riccardo Morabito
"""

from collections import Counter
from typing import Any

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.heatmap_plot import AbstractHeatmapPlot
from bench.domain.services.analytics_calculator import AnalyticsCalculator


_COOCCURRENCE_TOP_K = 14


class SqlSyntaxDistributionPlot(AbstractBarPlot):
    """01: Barplot della distribuzione delle feature SQL."""

    def __init__(self) -> None:
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(9, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "01_sql_syntax_distribution.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "01. Distribuzione Feature SQL"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Frequenza delle clausole e costrutti SQL generati all'interno delle query "
            "del benchmark."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza principale sui costrutti SQL."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0:
            return "Nessuna feature SQL registrata nel dataset."
        top_f, top_n = xs[0], ys[0]
        return (
            f"La clausola SQL piu' frequente e' '{top_f}', presente in {top_n} task del benchmark."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Feature SQL"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Frequenza Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae la distribuzione completa delle feature SQL presenti nei task."""
        counts: Counter = Counter()
        for t in tasks:
            for f in (t.get("spec") or {}).get("sql_features", []):
                counts[f] += 1
        items = counts.most_common()
        xs = [i[0] for i in items] or ["join"]
        ys = [i[1] for i in items] or [0]
        self._adapt_layout(len(xs))
        return xs, ys


class AstComplexityDepthPlot(AbstractBarPlot):
    """02: Barplot della profondità AST."""

    def __init__(self, calc: AnalyticsCalculator) -> None:
        """Inietta il calcolatore AST."""
        super().__init__(rotation=35, figsize=(9, 5.5))
        self._calc = calc

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "02_ast_complexity_depth.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "02. Profondità AST Query Gold"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Profondita' massima dell'albero sintattico (AST): misura l'annidamento "
            "logico delle query."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza sulla profondità delle query."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0:
            return "Nessun dato AST calcolato per le query."
        tot = sum(ys)
        max_idx = ys.index(max(ys))
        mode_depth, count = xs[max_idx], ys[max_idx]
        perc = round((count / tot) * 100, 1)
        return (
            f"Il {perc}% delle query ({count}/{tot}) presenta {mode_depth.lower()}, "
            f"evidenziando una struttura relazionale articolata."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Profondità AST"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Frequenza Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Calcola la profondità AST per le query Gold."""
        depths = [self._calc.parse_depth((t.get("gold") or {}).get("query", "")) for t in tasks]
        c = Counter(depths)
        return ([f"Profondità {k}" for k in sorted(c.keys())], [c[k] for k in sorted(c.keys())])


class SchemaDomainDiversityPlot(AbstractBarPlot):
    """03: Barplot della diversità dei domini."""

    def __init__(self) -> None:
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(9, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "03_schema_domain_diversity.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "03. Diversità Domini Aziendali Benchmark"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Distribuzione dei task nei 12 differenti scenari aziendali del benchmark "
            "(es. sanita', finanza, vendite)."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza sulla diversità settoriale."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0:
            return "Nessun dominio aziendale registrato."
        top_dom, top_n = xs[0], ys[0]
        tot_doms = len(xs)
        return (
            f"Il dominio piu' frequente e' '{top_dom}' ({top_n} task). "
            f"Il dataset copre uniformemente {tot_doms} settori industriali."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Dominio"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Numero Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae il conteggio per dominio."""
        c = Counter((t.get("spec") or {}).get("domain", "unknown") for t in tasks)
        items = c.most_common(8)
        return ([i[0] for i in items] or ["vendite"], [i[1] for i in items] or [0])


class SchemaComplexityHeatmapPlot(AbstractBarPlot):
    """04: Barplot della complessità dello schema."""

    def __init__(self) -> None:
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(9, 5.5))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "04_schema_complexity_heatmap.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "04. Complessità Schema (N. Tabelle)"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Numero di tabelle relazionali per schema: misura la complessita' "
            "e articolazione dei JOIN."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza sul numero di tabelle relazionali."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0:
            return "Nessun dato sulla dimensione dello schema."
        tot = sum(ys)
        max_idx = ys.index(max(ys))
        mode_tabs, count = xs[max_idx], ys[max_idx]
        perc = round((count / tot) * 100, 1)
        lo_label, hi_label = xs[0], xs[-1]
        return (
            f"La dimensione piu' frequente e' {mode_tabs.lower()} ({perc}% degli schemi); "
            f"il benchmark spazia da {lo_label} a {hi_label} ({len(xs)} cardinalita' distinte)."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N. Tabelle nello Schema"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Conteggio Schemi"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae il conteggio tabelle per schema."""
        c = Counter((t.get("spec") or {}).get("n_tables", 1) for t in tasks)
        labels = [f"{k} tabella" if k == 1 else f"{k} tabelle" for k in sorted(c.keys())]
        return (labels, [c[k] for k in sorted(c.keys())])


class SqlFeatureCooccurrencePlot(AbstractHeatmapPlot):
    """05: Heatmap di co-occorrenza delle feature SQL."""

    def __init__(self) -> None:
        """Inizializza la mappa; l'elenco feature è derivato dinamicamente dai task."""
        super().__init__(cmap="Blues", rotation=35, figsize=(13, 10))
        self._features: list[str] = []

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "05_sql_feature_cooccurrence.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "05. Co-occorrenza Costrutti SQL nelle Query"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Frequenza con cui i costrutti SQL piu' frequenti del run compaiono "
            "simultaneamente nella stessa query."
        )

    def insight(self, data: list[list[int]]) -> str:
        """Estrae la coppia di operatori con maggiore sinergia."""
        if not data or not any(sum(row) for row in data):
            return "Nessuna combinazione simultanea di operatori rilevata."
        max_val, best_i, best_j = 0, 0, 0
        for i, r in enumerate(data):
            for j, val in enumerate(r):
                if i != j and val > max_val:
                    max_val = val
                    best_i, best_j = i, j
        if max_val > 0:
            f1, f2 = self._features[best_i], self._features[best_j]
            return (
                f"La combinazione piu' frequente e' '{f1}' con '{f2}' ({max_val} query condivise)."
            )
        return "Gli operatori SQL sono distribuiti in modo ortogonale tra i task."

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "Feature SQL"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Feature SQL"

    @property
    def xticklabels(self) -> list[str]:
        """Restituisce le etichette delle colonne."""
        return self._features

    @property
    def yticklabels(self) -> list[str]:
        """Restituisce le etichette delle righe."""
        return self._features

    def prepare_data(self, tasks: list[dict[str, Any]]) -> list[list[int]]:
        """Calcola la matrice di co-occorrenza dei costrutti SQL piu' frequenti."""
        counts: Counter = Counter()
        for t in tasks:
            for f in (t.get("spec") or {}).get("sql_features", []):
                counts[f] += 1
        self._features = [f for f, _ in counts.most_common(_COOCCURRENCE_TOP_K)] or ["join"]
        self._adapt_layout(len(self._features))
        cooc: dict[str, dict[str, int]] = {
            f1: {f2: 0 for f2 in self._features} for f1 in self._features
        }
        for t in tasks:
            feats = set((t.get("spec") or {}).get("sql_features", []))
            for f1 in feats:
                if f1 in cooc:
                    for f2 in feats:
                        if f2 in cooc[f1]:
                            cooc[f1][f2] += 1
        return [[cooc[f1][f2] for f2 in self._features] for f1 in self._features]
