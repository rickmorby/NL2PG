"""Porta outbound per il rendering dei grafici scientifici del benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class PlotterPort(ABC):
    """Porta outbound astratta per il rendering grafico dei 16 grafici del benchmark."""

    @abstractmethod
    def render_plots(self, tasks: list[dict[str, Any]], output_dir: Path) -> None:
        """Renderizza e salva i 16 grafici scientifici nella directory specificata."""
