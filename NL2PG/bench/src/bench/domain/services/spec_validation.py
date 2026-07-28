"""Servizio di dominio per la validazione di una specifica Spec contro una categoria.

:author: Riccardo Morabito
"""

from bench.domain.models.category import CategoryDTO
from bench.domain.models.spec import SpecDTO


def validate_spec(spec: SpecDTO, category: CategoryDTO) -> tuple[bool, str]:
    """Verifica che twist, twist_rules e feature_sql della Spec siano coerenti con la categoria."""
    invalid_twists = set(spec.twist) - set(category.twist_ammessi)
    if invalid_twists:
        return False, f"twist fuori vocabolario: {sorted(invalid_twists)}"
    if spec.twist and not spec.twist_rules:
        return False, "twist presenti senza regole"
    if spec.twist and len(spec.twist_rules) < len(spec.twist):
        return (False,
                f"regole twist insufficienti ({len(spec.twist_rules)}/{len(spec.twist)})")
    invalid_features = set(spec.sql_features) - set(category.feature_sql)
    if invalid_features:
        return False, f"feature_sql fuori vocabolario: {sorted(invalid_features)}"
    return True, ""