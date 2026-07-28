"""Modulo dei servizi di dominio puri, senza dipendenze da infrastruttura.

:author: Riccardo Morabito
"""

from bench.domain.services.coverage_validator import CoverageValidator, CoverageResult
from bench.domain.services.domain_pool import DOMAIN_POOL
from bench.domain.services.feature_checker import FeatureChecker, FeatureCheckResult
from bench.domain.services.weighted_mean import weighted_mean

__all__: list[str] = [
    "CoverageValidator",
    "CoverageResult",
    "DOMAIN_POOL",
    "FeatureChecker",
    "FeatureCheckResult",
    "weighted_mean",
]
