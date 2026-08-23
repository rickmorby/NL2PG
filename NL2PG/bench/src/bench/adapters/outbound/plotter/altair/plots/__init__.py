"""Registro dei grafici ufficiali del benchmark (ordine numerico di presentazione)."""

from bench.adapters.outbound.plotter.altair.base import Plot
from bench.adapters.outbound.plotter.altair.plots.coverage import (
    HierarchyDistributionPlot,
    QueryTypeFeatureCoveragePlot,
    RowsPerTablePlot,
)
from bench.adapters.outbound.plotter.altair.plots.evaluation import (
    CriticByCalibrationOutcomePlot,
    GoldCardinalityPlot,
    PassRateByDifficultyPlot,
)
from bench.adapters.outbound.plotter.altair.plots.nl import (
    JargonFrequencyPlot,
    QuestionComplexityPlot,
    TwistTypeFrequencyPlot,
)
from bench.adapters.outbound.plotter.altair.plots.solvability import (
    FeaturePassRatePlot,
    PassRateBySchemaBandPlot,
    TwistDegradationPlot,
    TwistDifficultyPlot,
)
from bench.adapters.outbound.plotter.altair.plots.sql import (
    AstDepthDistributionPlot,
    DomainDistributionPlot,
    SchemaSizeDistributionPlot,
    SqlFeatureCooccurrencePlot,
    SqlFeatureDistributionPlot,
)


def get_default_plots() -> list[Plot]:
    """Restituisce i 18 grafici ufficiali nell'ordine di presentazione."""
    return [
        SqlFeatureDistributionPlot(),
        AstDepthDistributionPlot(),
        DomainDistributionPlot(),
        SchemaSizeDistributionPlot(),
        SqlFeatureCooccurrencePlot(),
        QuestionComplexityPlot(),
        TwistTypeFrequencyPlot(),
        JargonFrequencyPlot(),
        FeaturePassRatePlot(),
        TwistDegradationPlot(),
        TwistDifficultyPlot(),
        PassRateBySchemaBandPlot(),
        PassRateByDifficultyPlot(),
        CriticByCalibrationOutcomePlot(),
        GoldCardinalityPlot(),
        HierarchyDistributionPlot(),
        RowsPerTablePlot(),
        QueryTypeFeatureCoveragePlot(),
    ]
