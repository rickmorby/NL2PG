"""Generatori di valori univoci a partire dai valori template.

Per colonne PK/UNIQUE produce varianti deterministiche (email, codice fiscale,
stringa generica, intero sequenziale, data shiftata) evitando collisioni con i
valori gia' emessi e rispettando l'eventuale vincolo CHECK della colonna.

:author: Riccardo Morabito
"""

from contextlib import suppress
from typing import Any

from bench.domain.models.data import ColumnSchema
from bench.domain.services.data.check_constraints import satisfies_check
from bench.domain.services.data.column_types import is_date_type, is_integer_type, shift_value

_CF_LENGTH = 16
_ALPHABET_SIZE = 26
_MAX_SUFFIX_ATTEMPTS = 100


def _unique_email(base: str, idx: int, max_len: int | None) -> str:
    """Variante email: local+idx@domain, rispettando max_length."""
    local, domain = base.split("@", 1)
    cand = f"{local}{idx}@{domain}"
    if max_len is not None and len(cand) > max_len:
        max_local = max_len - len(f"{idx}@{domain}")
        local = local[: max(1, max_local)]
        cand = f"{local}{idx}@{domain}"
    return cand


def _unique_cf(base: str, idx: int, max_len: int | None) -> str:
    """Variante codice fiscale: suffisso lettera o rotazione del serial."""
    if idx < _ALPHABET_SIZE:
        cand = base[: _CF_LENGTH - 1] + chr(ord("A") + idx)
    else:
        try:
            serial = int(base[12:15])
        except ValueError:
            serial = 0
        new_serial = (serial + idx) % 1000
        last = chr(ord("A") + (idx % _ALPHABET_SIZE))
        cand = f"{base[:12]}{new_serial:03d}{last}"
    if max_len is not None and len(cand) > max_len:
        cand = cand[:max_len]
    return cand


def _unique_string(base: str, idx: int, max_len: int | None, check: str | None = None) -> str:
    """Genera una variante stringa unica (email/CF/generico/numerico).

    Con ``check`` fornito la variante viene validata contro il vincolo e
    rigenerata (fino a ``_MAX_SUFFIX_ATTEMPTS``) finche' non conforme.
    """
    candidate = _string_variant(base, idx, max_len)
    if check is None or satisfies_check(candidate, check):
        return candidate
    for attempt in range(1, _MAX_SUFFIX_ATTEMPTS + 1):
        candidate = _string_variant(base, idx + attempt, max_len)
        if satisfies_check(candidate, check):
            return candidate
    return candidate


def _string_variant(base: str, idx: int, max_len: int | None) -> str:
    """Produce la idx-esima variante della stringa base senza validazione CHECK."""
    if idx == 0:
        return base
    if "@" in base:
        return _unique_email(base, idx, max_len)
    if len(base) == _CF_LENGTH and base[:6].isalpha() and base[:6].isupper():
        return _unique_cf(base, idx, max_len)
    cand = f"{base}{idx}"
    if max_len is not None and len(cand) > max_len:
        max_base = max_len - len(str(idx))
        cand = f"{base[: max(1, max_base)]}{idx}"
    if base.isdigit():
        with suppress(ValueError):
            numeric = str(int(base) + idx).zfill(len(base))
            if (max_len is None or len(numeric) <= max_len) and len(numeric) < len(cand):
                return numeric
    return cand


def generate_unique(
    column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
) -> Any:
    """Genera un valore univoco dal template per colonna int/data/stringa."""
    if is_integer_type(column.data_type):
        base = template_value if isinstance(template_value, int) else 1
        candidate = base + instance_index
        while candidate in used:
            candidate += 1
    elif is_date_type(column.data_type) and isinstance(template_value, str):
        candidate = shift_value(template_value, column, instance_index)
        suffix = 1
        while candidate in used:
            candidate = shift_value(template_value, column, instance_index + suffix)
            suffix += 1
    else:
        base = template_value if template_value is not None else column.name
        base_str = str(base)
        check = getattr(column, "check_expr", None)
        candidate = (
            base_str
            if instance_index == 0
            else _unique_string(base_str, instance_index, column.max_length)
        )
        suffix = 1
        while candidate in used or not satisfies_check(candidate, check):
            candidate = _unique_string(base_str, instance_index + suffix, column.max_length)
            suffix += 1
            if suffix > _MAX_SUFFIX_ATTEMPTS:
                candidate = f"{base_str}_{instance_index + suffix}"
                break
    used.add(candidate)
    return candidate
