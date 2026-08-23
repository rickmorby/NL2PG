"""Sottopacchetto di plotting dichiarativo basato su Altair (Vega-Lite).

Gerarchia: ``theme`` (identita' visiva) -> ``base`` (Template Method ``Plot``)
-> ``builders`` (forme grafiche condivise) -> ``plots`` (specifiche dei singoli
grafici) -> ``adapter`` (porta ``PlotterPort`` ed export PNG @2x + SVG).
"""

from bench.adapters.outbound.plotter.altair.adapter import AltairPlotterAdapter

__all__ = ["AltairPlotterAdapter"]
