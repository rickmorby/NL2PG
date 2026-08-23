"""Generazione delle righe per tabella: facciata dei moduli specializzati.

Il pipeline e' scomposto per responsabilita': ``check_constraints`` valida i
vincoli CHECK, ``unique_values`` genera le varianti univoche, ``email_coherence``
garantisce l'allineamento anagrafico dell'email, ``row_builder`` assembla la
riga singola e ``row_expander`` orchestra l'espansione dei template. I volumi
sono calcolati da ``RowCounter``.

:author: Riccardo Morabito
"""

from bench.domain.services.data.row_builder import RowBuilder
from bench.domain.services.data.row_expander import RowExpander

__all__: list[str] = ["RowBuilder", "RowExpander"]
