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
        return "06. Complessità Linguistica vs N. Tabelle"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Rapporto tra la lunghezza del testo naturale (storia + domanda) "
            "e la dimensione dello schema."
        )

    def insight(self, data: tuple[list[int], list[int]]) -> str:
        """Estrae l'evidenza sulla ricchezza descrittiva dei testi."""
        _tables, words = data
        if not words:
            return "Nessun testo analizzato nei task."
        avg_w = round(sum(words) / len(words), 1)
        min_w, max_w = min(words), max(words)
        return (
            f"I testi hanno una lunghezza media di {avg_w} parole "
            f"(range: {min_w} - {max_w} parole), ricchi di contesto aziendale."
        )

    def xlabel(self) -> str:
        """Restituisce l'etichetta dell'asse X."""
        return "N. Tabelle Schema"

    def ylabel(self) -> str:
        """Restituisce l'etichetta dell'asse Y."""
        return "Lunghezza Testo (Parole)"

    def prepare_data(self, tasks: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
        """Estrae conteggio parole e numero tabelle."""
        words = [
            len(((t.get("story") or "") + " " + (t.get("question") or "")).split()) for t in tasks
        ]
        tables = [(t.get("spec") or {}).get("n_tables", 1) for t in tasks]
        return tables, words

    def draw(self, ax: Any, data: tuple[list[int], list[int]]) -> None:
        """Disegna uno scatterplot Seaborn."""
        tables, words = data
        scatterplot(x=tables, y=words, color="#e67e22", s=70, ax=ax)


class TwistTypeFrequencyPlot(AbstractBarPlot):
    """07: Barplot della frequenza dei twist."""

    def __init__(self) -> None:
        """Inizializza la rotazione e la dimensione del grafico."""
        super().__init__(rotation=35, figsize=(9.2, 5.8))

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "07_twist_type_frequency.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "07. Frequenza Disturbi Semantici (Twist)"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Frequenza delle tipologie di disturbo semantico (Twist) inserite per "
            "testare la robustezza dei modelli."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza sulla tipologia di disturbo dominante."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0:
            return "Nessun disturbo semantico presente."
        top_tw, top_n = xs[0], ys[0]
        return (
            f"Il disturbo piu' frequente e' '{top_tw}' ({top_n} regole), "
            f"per saggiare il disallineamento lessicale."
        )

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
            for tr in (t.get("spec") or {}).get("twist_rules", []):
                c[tr.get("twist_type", "unknown")] += 1
        items = c.most_common(6)
        return (
            [i[0] for i in items] if items else ["baseline"],
            [i[1] for i in items] if items else [len(tasks)],
        )


class VocabularyJargonDistributionPlot(AbstractBarPlot):
    """08: Barplot della distribuzione del gergo."""

    def __init__(self) -> None:
        """Inizializza la rotazione, dimensione e margine per etichette lunghe."""
        super().__init__(rotation=35, figsize=(9.2, 5.8), bottom_margin=0.30)

    def filename(self) -> str:
        """Restituisce il nome del file PNG."""
        return "08_vocabulary_jargon_distribution.png"

    def title(self) -> str:
        """Restituisce il titolo del grafico."""
        return "08. Frequenza Gergo e Sinonimi nei Twist"

    def description(self) -> str:
        """Restituisce la descrizione metodologica del grafico."""
        return (
            "Frequenza dei termini di gergo aziendale e acronimi inseriti nelle storie "
            "per mascherare lo schema."
        )

    def insight(self, data: tuple[list[str], list[int]]) -> str:
        """Estrae l'evidenza sui termini di gergo obsoleti."""
        xs, ys = data
        if not xs or not ys or sum(ys) == 0 or xs[0] == "nessun_gergo":
            return "Nessun termine di gergo obsoleto registrato."
        top_j, top_n = xs[0], ys[0]
        return (
            f"Il termine gergale piu' frequente e' '{top_j}' ({top_n} occorrenze), "
            f"richiedendo disambiguazione semantica."
        )

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
            for tr in (t.get("spec") or {}).get("twist_rules", [])
            if tr.get("obsolete_value")
        ]
        top = Counter(obs).most_common(6)
        return ([i[0] for i in top] or ["nessun_gergo"], [i[1] for i in top] or [0])
