"""Classi di plotting per la complessità del linguaggio naturale e dei twist.

:author: Riccardo Morabito
"""

from collections import Counter
from typing import Any

from seaborn import scatterplot

from bench.adapters.outbound.plotter.bar_plot import AbstractBarPlot
from bench.adapters.outbound.plotter.base import AbstractPlot


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
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(9.5, 5.5))

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
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(9.5, 5.5))

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
