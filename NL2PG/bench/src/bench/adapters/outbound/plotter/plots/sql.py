"""Classi di plotting per la sintassi SQL e la struttura del database.

:author: Riccardo Morabito
"""

from collections import Counter
from typing import Any

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.heatmap_plot import AbstractHeatmapPlot
from bench.domain.services.analytics_calculator import AnalyticsCalculator


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
            for f in (t.get("spec") or {}).get("sql_features", []):
                counts[f] += 1
        items = counts.most_common(8)
        return ([i[0] for i in items] or ["join"], [i[1] for i in items] or [0])


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
        return "04. Complessità Schema (N° Tabelle)"

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N° Tabelle"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Conteggio Task"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
        """Estrae la distribuzione del numero di tabelle."""
        c = Counter((t.get("spec") or {}).get("n_tables", 1) for t in tasks)
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
            feats = set((t.get("spec") or {}).get("sql_features", []))
            for i, f1 in enumerate(self._top_feats):
                for j, f2 in enumerate(self._top_feats):
                    if f1 in feats and f2 in feats:
                        matrix[i][j] += 1
        return matrix
