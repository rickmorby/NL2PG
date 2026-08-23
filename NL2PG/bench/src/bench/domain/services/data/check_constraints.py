"""Validazione dei vincoli CHECK di colonna su valori generati.

Interpreta le espressioni CHECK piu' comuni nei DDL sintetici (regex ``~``/``~*``,
``length()``, ``BETWEEN``, confronti numerici, liste ``IN``) per garantire che
ogni valore prodotto rispetti il contratto dichiarato dallo schema.

:author: Riccardo Morabito
"""

from contextlib import suppress
from re import IGNORECASE, error, search
from re import compile as re_compile

_RE_CHECK_REGEX = re_compile(r"~\*?\s*'([^']+)'")
_RE_CHECK_LENGTH = re_compile(r"length\s*\(\s*\w+\s*\)\s*([<>]=?|=)\s*(\d+)", IGNORECASE)
_RE_CHECK_BETWEEN = re_compile(
    r"(?:VALUE|[a-zA-Z0-9_]+)\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)",
    IGNORECASE,
)
_RE_CHECK_CMP = re_compile(
    r"(?:VALUE|[a-zA-Z0-9_]+)\s*(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)", IGNORECASE
)
_RE_CHECK_IN = re_compile(r"(?:VALUE|[a-zA-Z0-9_]+)\s+IN\s*\(([^)]+)\)", IGNORECASE)


def _check_regex_part(value: str, part: str) -> bool | None:
    """Valida la componente regex del vincolo, se presente."""
    m = _RE_CHECK_REGEX.search(part)
    if not m:
        return None
    try:
        return bool(search(m.group(1), value))
    except error:
        return True


def _check_length_part(value: str, part: str) -> bool | None:
    """Valida la componente ``length()`` del vincolo, se presente."""
    ml = _RE_CHECK_LENGTH.search(part)
    if not ml:
        return None
    op, num = ml.group(1), int(ml.group(2))
    lv = len(value)
    checks = {
        ">=": lv >= num,
        ">": lv > num,
        "<=": lv <= num,
        "<": lv < num,
        "=": lv == num,
    }
    return checks.get(op, True)


def _check_numeric_parts(val_num: float, check_expr: str) -> bool:
    """Valida i vincoli BETWEEN e di confronto numerico sull'intera espressione."""
    for m in _RE_CHECK_BETWEEN.finditer(check_expr):
        low, high = float(m.group(1)), float(m.group(2))
        if not (low <= val_num <= high):
            return False
    clean_check = _RE_CHECK_BETWEEN.sub("", check_expr)
    for m in _RE_CHECK_CMP.finditer(clean_check):
        op, limit = m.group(1), float(m.group(2))
        if (
            (op == ">=" and val_num < limit)
            or (op == ">" and val_num <= limit)
            or (op == "<=" and val_num > limit)
            or (op == "<" and val_num >= limit)
            or (op == "=" and val_num != limit)
        ):
            return False
    return True


def satisfies_check(value: object, check_expr: str | None) -> bool:
    """Indica se ``value`` soddisfa l'espressione CHECK della colonna.

    Valuta in sequenza vincoli numerici, liste IN e componenti regex/length
    combinate con AND; assenza di vincolo o valore NULL sono sempre validi.
    """
    if not check_expr or value is None:
        return True
    val_str = str(value).strip("'")
    val_num = None
    with suppress(ValueError, TypeError):
        val_num = float(val_str)

    if val_num is not None and not _check_numeric_parts(val_num, check_expr):
        return False

    for m in _RE_CHECK_IN.finditer(check_expr):
        allowed = [x.strip().strip("'\"") for x in m.group(1).split(",")]
        if val_str not in allowed:
            return False

    for raw_part in check_expr.split(" AND "):
        part = raw_part.strip()
        res = _check_regex_part(val_str, part)
        if res is not None:
            if not res:
                return False
            continue
        res = _check_length_part(val_str, part)
        if res is not None and not res:
            return False
    return True
