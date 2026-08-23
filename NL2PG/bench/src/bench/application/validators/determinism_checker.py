"""Regole di riproducibilità del gold result di una query SQL.

Una query order_sensitive richiede ORDER BY esplicito, LIMIT senza ordinamento
produce sottoinsiemi non deterministici e le funzioni temporali volatili
renderebbero il risultato non confrontabile tra esecuzioni.

:author: Riccardo Morabito
"""

from re import IGNORECASE
from re import compile as re_compile

from sqlglot import exp

_RE_VOLATILE_TEXT = re_compile(
    r"\b(?:NOW\s*\(|LOCALTIME(?:STAMP)?\b|CLOCK_TIMESTAMP|TRANSACTION_TIMESTAMP|"
    r"STATEMENT_TIMESTAMP)",
    flags=IGNORECASE,
)


def check_determinism(order_sensitive: bool, tree: exp.Expression) -> str:
    """Verifica le regole di riproducibilità; restituisce il messaggio d'errore o vuoto."""
    if order_sensitive and not has_root_order_by(tree):
        return (
            "La query ha order_sensitive=true ma manca della clausola ORDER BY "
            "nella query principale della SELECT."
        )
    if tree.find(exp.Limit) and not has_root_order_by(tree):
        return (
            "La query usa LIMIT senza ORDER BY nella SELECT principale: le righe "
            "restituite non sarebbero deterministiche. Aggiungi un ORDER BY che definisca "
            "quale sottoinsieme di righe selezionare prima del LIMIT."
        )
    volatile = volatile_time_function(tree)
    if volatile:
        return (
            f"La query usa la funzione temporale volatile '{volatile}': il risultato "
            "cambierebbe a ogni esecuzione rendendo il gold non riproducibile. Usa una "
            "data/ora fissa come letterale (es. DATE '2026-08-21') eventualmente combinata "
            "con INTERVAL."
        )
    return ""


def has_root_order_by(tree: exp.Expression) -> bool:
    """Verifica che la query contenga la clausola ORDER BY a livello radice."""
    return tree.args.get("order") is not None


def volatile_time_function(tree: exp.Expression) -> str | None:
    """Restituisce il nome della funzione temporale volatile usata, se presente.

    CURRENT_DATE/NOW e simili rendono il gold result non riproducibile: il solver
    eseguito in un giorno diverso otterrebbe righe diverse per le stesse domande.
    """
    for cls, name in (
        (exp.CurrentDate, "CURRENT_DATE"),
        (exp.CurrentTimestamp, "CURRENT_TIMESTAMP"),
        (exp.CurrentTime, "CURRENT_TIME"),
        (exp.CurrentDatetime, "CURRENT_DATETIME"),
    ):
        if tree.find(cls):
            return name
    if _RE_VOLATILE_TEXT.search(tree.sql(dialect="postgres")):
        return "NOW/LOCALTIMESTAMP"
    return None
