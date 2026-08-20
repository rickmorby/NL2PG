"""Servizio di dominio per validazione e calcolo hash di una SpecDTO.

:author: Riccardo Morabito
"""

from hashlib import sha256

from orjson import OPT_SORT_KEYS, dumps as orjson_dumps

from bench.domain.models.category import CategoryDTO
from bench.domain.models.spec import SpecDTO


def compute_spec_hash(category: str, spec: SpecDTO) -> str:
    """Calcola l'hash SHA-256 deterministico per una SpecDTO e la sua categoria."""
    payload = orjson_dumps(
        {
            "cat": category,
            "domain": spec.domain,
            "n_tables": spec.n_tables,
            "sql_features": sorted(spec.sql_features),
            "twist": sorted(spec.twist),
            "rules": sorted(
                (r.model_dump() for r in spec.twist_rules),
                key=lambda r: orjson_dumps(r, option=OPT_SORT_KEYS),
            ),
        },
        option=OPT_SORT_KEYS,
    )
    return sha256(payload).hexdigest()[:16]


def _validate_n_tables(spec: SpecDTO, category: CategoryDTO, target_n_tables: int) -> str | None:
    """Restituisce l'errore di n_tables oppure None se il valore è valido."""
    lo, hi = category.n_tables_range
    if not (lo <= spec.n_tables <= hi):
        return f"n_tables={spec.n_tables} fuori range [{lo},{hi}] della categoria"
    if target_n_tables and spec.n_tables != target_n_tables:
        return (
            f"n_tables={spec.n_tables} diverso dal valore deterministico richiesto "
            f"{target_n_tables}"
        )
    return None


def validate_spec(
    spec: SpecDTO,
    category: CategoryDTO,
    target_domain: str = "",
    target_n_tables: int = 0,
) -> tuple[bool, str]:
    """Verifica che dominio, twist, twist_rules, feature_sql e n_tables siano coerenti."""
    if target_domain and spec.domain != target_domain:
        return (
            False,
            f"dominio '{spec.domain}' non corrisponde al target_domain richiesto '{target_domain}'",
        )
    n_tables_err = _validate_n_tables(spec, category, target_n_tables)
    if n_tables_err:
        return False, n_tables_err
    invalid_twists = set(spec.twist) - set(category.twist_ammessi)
    if invalid_twists:
        return False, f"twist fuori vocabolario: {sorted(invalid_twists)}"
    if spec.twist and len(spec.twist_rules) < len(spec.twist):
        detail = (
            "twist presenti senza regole"
            if not spec.twist_rules
            else f"regole twist insufficienti ({len(spec.twist_rules)}/{len(spec.twist)})"
        )
        return False, detail
    invalid_features = set(spec.sql_features) - set(category.feature_sql)
    if invalid_features:
        return False, f"feature_sql fuori vocabolario: {sorted(invalid_features)}"
    return True, ""
