"""Grafici scientifici del solver: accuratezza, impatto e diagnostica errori."""

from solver.adapters.outbound.plotter.altair.plots.accuracy import (
    DifficultyAccuracyPlot,
    DomainAccuracyPlot,
    GeneratedSchemaAccuracyPlot,
    RecipeAccuracyPlot,
    SchemaSizeAccuracyPlot,
    SchemaStageAccuracyPlot,
)
from solver.adapters.outbound.plotter.altair.plots.impact import (
    ErrorTaxonomyPlot,
    ExecutionSpeedPlot,
    FeatureImpactPlot,
    RecipeErrorHeatmapPlot,
    TranslationModePlot,
    TwistImpactPlot,
)
from solver.adapters.outbound.plotter.altair.base import Plot

__all__ = [
    "DifficultyAccuracyPlot",
    "DomainAccuracyPlot",
    "ErrorTaxonomyPlot",
    "ExecutionSpeedPlot",
    "FeatureImpactPlot",
    "GeneratedSchemaAccuracyPlot",
    "Plot",
    "RecipeAccuracyPlot",
    "RecipeErrorHeatmapPlot",
    "SchemaSizeAccuracyPlot",
    "SchemaStageAccuracyPlot",
    "TranslationModePlot",
    "TwistImpactPlot",
]


def get_default_plots() -> list[Plot]:
    """Suite ufficiale dei 12 grafici della run del solver, in ordine di presentazione."""
    return [
        RecipeAccuracyPlot(),
        GeneratedSchemaAccuracyPlot(),
        DomainAccuracyPlot(),
        DifficultyAccuracyPlot(),
        SchemaSizeAccuracyPlot(),
        SchemaStageAccuracyPlot(),
        TwistImpactPlot(),
        FeatureImpactPlot(),
        ErrorTaxonomyPlot(),
        RecipeErrorHeatmapPlot(),
        TranslationModePlot(),
        ExecutionSpeedPlot(),
    ]
