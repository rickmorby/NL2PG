"""Modulo dei servizi di dominio puri, senza dipendenze da infrastruttura.

:author: Riccardo Morabito
"""

from bench.domain.services.feature_checker import FeatureChecker, FeatureCheckResult
from bench.domain.services.coverage_validator import CoverageValidator, CoverageResult

__all__: list[str] = [
    "FeatureChecker",
    "FeatureCheckResult",
    "CoverageValidator",
    "CoverageResult",
]
