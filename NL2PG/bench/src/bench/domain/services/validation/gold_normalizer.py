"""Normalizzazione canonica delle celle del risultato gold (servizio di dominio puro).

Garantisce due invarianti del benchmark:
1. i valori temporali sono proiettati sulla rappresentazione ``str()`` prodotta dai
   driver PostgreSQL a runtime, così lo storage JSON resta coerente con il confronto
   indipendentemente dal serializzatore;
2. nessuna cella testuale può contenere i letterali 'none'/'null': il mondo SQL esprime
   l'assenza di valore con il keyword NULL e mai con una stringa.

:author: Riccardo Morabito
"""

import re
from datetime import date, datetime
from typing import Any

_NONE_LIKE = re.compile(r"^(none|null)$", re.IGNORECASE)

_ERROR_NONE_LITERAL = (
    "Il risultato contiene la stringa {cell!r}: usare il keyword SQL NULL, "
    "mai il letterale testuale 'None'/'null'."
)


def canonicalize_cell(value: Any) -> Any:
    """Proietta le celle temporali sulla loro forma testuale canonica.

    I ``datetime``/``date`` diventano ``str(value)`` (separatore spazio per datetime),
    allineando lo storage alla rappresentazione runtime; ogni altro tipo transita
    immutato.
    """
    if isinstance(value, datetime | date):
        return str(value)
    return value


def canonicalize_rows(rows: list[tuple] | list[list[Any]]) -> list[list[Any]]:
    """Applica :func:`canonicalize_cell` a ogni cella di ogni riga."""
    return [[canonicalize_cell(cell) for cell in row] for row in rows]


def find_none_literal(rows: list[list[Any]]) -> str | None:
    """Restituisce un messaggio d'errore se una cella è un letterale none/null, altrimenti None."""
    for row in rows:
        for cell in row:
            if isinstance(cell, str) and _NONE_LIKE.fullmatch(cell.strip()):
                return _ERROR_NONE_LITERAL.format(cell=cell)
    return None
