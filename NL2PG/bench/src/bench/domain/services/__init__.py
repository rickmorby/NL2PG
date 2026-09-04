"""Modulo dei servizi di dominio puri, senza dipendenze da infrastruttura.

:author: Riccardo Morabito
"""

from bench.domain.services.analytics.analytics_calculator import AnalyticsCalculator
from bench.domain.services.analytics.weighted_mean import weighted_mean
from bench.domain.services.picking.category_round_picker import CategoryRoundPicker
from bench.domain.services.picking.domain_pool import DOMAIN_POOL
from bench.domain.services.picking.role_example_builder import RoleExampleBuilder
from bench.domain.services.validation.coverage_validator import CoverageResult, CoverageValidator
from bench.domain.services.validation.feature_checker import FeatureCheckResult, FeatureChecker
from bench.domain.services.validation.narrative_repair import NarrativeRepair
from bench.domain.services.validation.result_comparator import ResultComparator
from bench.domain.services.validation.schema_type_checker import SchemaTypeChecker
from bench.domain.services.validation.spec_validation import validate_spec
from bench.domain.services.validation.sql_repair import PostgresSQLRepair

__all__: list[str] = [
    "DOMAIN_POOL",
    "AnalyticsCalculator",
    "CategoryRoundPicker",
    "CoverageResult",
    "CoverageValidator",
    "FeatureCheckResult",
    "FeatureChecker",
    "NarrativeRepair",
    "PostgresSQLRepair",
    "ResultComparator",
    "RoleExampleBuilder",
    "SchemaTypeChecker",
    "validate_spec",
    "weighted_mean",
]
