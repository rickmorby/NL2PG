"""Selettore a giri delle categorie per la generazione batch dei task.

:author: Riccardo Morabito
"""

from collections import deque
from random import sample
from typing import Sequence


class CategoryRoundPicker:
    """Seleziona le categorie a giri completi, con rotazione e senza esclusioni.

    Ogni categoria è organizzata per livello, dove il livello corrisponde al
    numero di task accettati per quella categoria. La selezione avviene sempre
    dal livello più basso non vuoto: in questo modo una run con ``count`` task
    accettati distribuisce la richiesta in ``count // M`` giri completi sulle M
    categorie più un giro parziale di ``count % M`` categorie.

    Una categoria che fallisce torna in coda allo stesso livello (rotazione):
    non viene mai esclusa, garantendo che la distribuzione richiesta venga
    prima o poi completata.
    """

    def __init__(
        self,
        categories: Sequence[str],
        accepted_counts: dict[str, int] | None = None,
    ) -> None:
        """Inizializza il selettore dai conteggi accepted, o dal livello zero."""
        counts = accepted_counts or {}
        unknown = set(counts) - set(categories)
        if unknown:
            raise ValueError(f"Conteggi accepted per categorie sconosciute: {sorted(unknown)}")
        self._levels: dict[int, deque[str]] = {}
        shuffled = sample(list(categories), len(categories))
        for category in shuffled:
            level = counts.get(category, 0)
            self._levels.setdefault(level, deque()).append(category)
        self._pending: dict[str, int] = {}
        self._failures: dict[str, int] = {}

    def pick(self) -> str | None:
        """Restituisce la categoria al livello più basso, rimuovendola dalla coda.

        Returns:
            La categoria selezionata, oppure ``None`` quando nessuna categoria
            è disponibile (tutte in volo o distribuzione completata).

        """
        for level in sorted(self._levels):
            queue = self._levels[level]
            if queue:
                category = queue.popleft()
                self._pending[category] = level
                return category
        return None

    def resolve(self, category: str, accepted: bool) -> int:
        """Registra l'esito del task e restituisce i fallimenti consecutivi della categoria.

        L'accettazione promuove la categoria al livello successivo e azzera il
        contatore; il fallimento la rimette in coda allo stesso livello.
        """
        level = self._pending.pop(category, 0)
        if accepted:
            self._failures[category] = 0
            self._levels.setdefault(level + 1, deque()).append(category)
            return 0
        self._levels.setdefault(level, deque()).append(category)
        failures = self._failures.get(category, 0) + 1
        self._failures[category] = failures
        return failures
