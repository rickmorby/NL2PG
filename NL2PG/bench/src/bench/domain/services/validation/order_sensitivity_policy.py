"""Policy deterministica di coerenza per il flag ``order_sensitive`` del risultato gold.

Le due regole allineano il flag alla semantica della question italiana:

D1 — se la question richiede esplicitamente un ordinamento dell'OUTPUT (forme verbali
     come "ordina l'elenco", "disponendo i risultati", "in ordine alfabetico") e la
     query gold possiede un ORDER BY esterno, il flag DEVE essere True;
D2 — se la question non contiene alcun linguaggio d'ordinamento e la query non applica
     LIMIT/OFFSET (che impongono comunque determinismo), il flag deve essere False:
     i superlativi di selezione ("il cliente più recente...") non sono ordinamenti.

Il riconoscimento è lessicale e conservativo: copre le forme verbali italiane e
ignora deliberatamente i sostantivi di dominio ("ordine/ordini" come entità) e gli
aggregati ("il peso massimo registrato"), minimizzando i falsi positivi.

:author: Riccardo Morabito
"""

from re import DOTALL, IGNORECASE, compile as re_compile

_RE_ORDER_OUTPUT = re_compile(
    r"(ordinando|ordinare|\bordinat[oaie]\b|\bordina\b|disponendo|dispost[ei]\b"
    r"|in ordine\s+\w+|alfabetic\w*|decrescent\w*|crescent\w*|cronologic\w*"
    r"|\bclassifica\b|graduatoria"
    r"|\bdal pi(ù|u') \w+ (al|alla) pi(ù|u')|\bdalla \w+ pi(ù|u') recent"
    r"|partendo dal)",
    IGNORECASE,
)

_RE_LIMIT_OFFSET = re_compile(r"\b(LIMIT|OFFSET)\b", IGNORECASE)

_RE_WINDOW_OVER = re_compile(r"OVER\s*\([^)]*\)", IGNORECASE | DOTALL)

_RE_ORDER_BY = re_compile(r"\bORDER\s+BY\b", IGNORECASE)


def question_requests_output_order(question: str) -> bool:
    """Rileva se la question chiede esplicitamente l'ordinamento del risultato."""
    return _RE_ORDER_OUTPUT.search(question) is not None


def query_has_outer_order_by(query: str) -> bool:
    """Rileva un ORDER BY esterno, ignorando quelli dentro window function ``OVER ()``."""
    return _RE_ORDER_BY.search(_RE_WINDOW_OVER.sub("", query)) is not None


def resolve_order_sensitive(question: str, query: str, declared: bool) -> tuple[bool, str]:
    """Applica le regole D1/D2 e restituisce ``(flag_coerente, motivazione)``.

    ``motivazione`` è vuota quando il flag dichiarato è già conforme; altrimenti
    descrive brevemente la normalizzazione applicata (per logging/feedback).
    """
    hinted = question_requests_output_order(question)
    limited = _RE_LIMIT_OFFSET.search(query) is not None

    if not declared and hinted and query_has_outer_order_by(query):
        return True, (
            "order_sensitive promosso a True: la question richiede esplicitamente "
            "un ordinamento e la gold query lo produce"
        )
    if declared and not hinted and not limited:
        return False, (
            "order_sensitive degradato a False: la question non esprime alcun "
            "criterio d'ordinamento e la query non usa LIMIT/OFFSET"
        )
    return declared, ""
