"""Modulo package contenente i 16 grafici scientifici polimorfici raggruppati per categoria.

:author: Riccardo Morabito
"""

from bench.adapters.outbound.plotter.base import AbstractPlot
from bench.adapters.outbound.plotter.plots.evaluation import (
    Critic5DimensionsRadarPlot,
    CriticVsPassrateCorrelationPlot,
    QueryResultCardinalityDistributionPlot,
    SolverPassrateByDifficultyPlot,
)
from bench.adapters.outbound.plotter.plots.nl import (
    NlLinguisticComplexityPlot,
    TwistTypeFrequencyPlot,
    VocabularyJargonDistributionPlot,
)
from bench.adapters.outbound.plotter.plots.solvability import (
    SchemaSizeVsPassrateBoxplotPlot,
    SqlFeaturePassrateImpactPlot,
    TwistCountDegradationCurvePlot,
    TwistVsDifficultyHeatmapPlot,
)
from bench.adapters.outbound.plotter.plots.sql import (
    AstComplexityDepthPlot,
    SchemaComplexityHeatmapPlot,
    SchemaDomainDiversityPlot,
    SqlFeatureCooccurrencePlot,
    SqlSyntaxDistributionPlot,
)
from bench.domain.services.analytics_calculator import AnalyticsCalculator


def get_default_plots(calculator: AnalyticsCalculator) -> list[AbstractPlot]:
    """Restituisce la lista ordinata dei 16 grafici scientifici polimorfici del benchmark."""
    return [
        SqlSyntaxDistributionPlot(),
        AstComplexityDepthPlot(calculator),
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


__all__ = [
    "get_default_plots",
    "SqlSyntaxDistributionPlot",
    "AstComplexityDepthPlot",
    "SchemaDomainDiversityPlot",
    "SchemaComplexityHeatmapPlot",
    "SqlFeatureCooccurrencePlot",
    "NlLinguisticComplexityPlot",
    "TwistTypeFrequencyPlot",
    "VocabularyJargonDistributionPlot",
    "SqlFeaturePassrateImpactPlot",
    "TwistCountDegradationCurvePlot",
    "TwistVsDifficultyHeatmapPlot",
    "SchemaSizeVsPassrateBoxplotPlot",
    "SolverPassrateByDifficultyPlot",
    "CriticVsPassrateCorrelationPlot",
    "Critic5DimensionsRadarPlot",
    "QueryResultCardinalityDistributionPlot",
]
