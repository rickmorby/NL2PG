"""Servizi di validazione e verifica."""

from bench.domain.services.validation.coverage_validator import CoverageResult, CoverageValidator
from bench.domain.services.validation.feature_checker import FeatureCheckResult, FeatureChecker
from bench.domain.services.validation.narrative_repair import NarrativeRepair
from bench.domain.services.validation.result_comparator import ResultComparator
from bench.domain.services.validation.schema_type_checker import SchemaTypeChecker
from bench.domain.services.validation.spec_validation import validate_spec
from bench.domain.services.validation.sql_repair import PostgresSQLRepair

__all__ = [
    "CoverageResult",
    "CoverageValidator",
    "FeatureCheckResult",
    "FeatureChecker",
    "NarrativeRepair",
    "PostgresSQLRepair",
    "ResultComparator",
    "SchemaTypeChecker",
    "validate_spec",
]
