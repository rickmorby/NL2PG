"""Servizio di dominio per validazione e calcolo hash di una SpecDTO.

:author: Riccardo Morabito
"""

from hashlib import sha256
from json import dumps

from bench.domain.models.category import CategoryDTO
from bench.domain.models.spec import SpecDTO


def compute_spec_hash(category: str, spec: SpecDTO) -> str:
    """Calcola l'hash SHA-256 deterministico per una SpecDTO e la sua categoria."""
    payload = dumps(
        {
            "cat": category,
            "domain": spec.domain,
            "sql_features": sorted(spec.sql_features),
            "twist": sorted(spec.twist),
            "rules": sorted([r.model_dump_json() for r in spec.twist_rules]),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_spec(
    spec: SpecDTO, category: CategoryDTO, target_domain: str = ""
) -> tuple[bool, str]:
    """Verifica che dominio, twist, twist_rules e feature_sql della Spec siano coerenti."""
    if target_domain and spec.domain != target_domain:
        return (
            False,
            f"dominio '{spec.domain}' non corrisponde al target_domain richiesto '{target_domain}'",
        )
    invalid_twists = set(spec.twist) - set(category.twist_ammessi)
    if invalid_twists:
        return False, f"twist fuori vocabolario: {sorted(invalid_twists)}"
    if spec.twist and not spec.twist_rules:
        return False, "twist presenti senza regole"
    if spec.twist and len(spec.twist_rules) < len(spec.twist):
        return (
            False,
            f"regole twist insufficienti ({len(spec.twist_rules)}/{len(spec.twist)})",
        )
    invalid_features = set(spec.sql_features) - set(category.feature_sql)
    if invalid_features:
        return False, f"feature_sql fuori vocabolario: {sorted(invalid_features)}"
    return True, ""
