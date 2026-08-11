"""Modulo package delle eccezioni personalizzate del benchmark.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException
from bench.domain.exceptions.clients_exc import (
    DatabaseClientError,
    LLMClientError,
    ModelOutputContractError,
    ProviderConfigError,
    SpecDuplicatedError,
)
from bench.domain.exceptions.config_exc import ConfigurationMissingFieldError
from bench.domain.exceptions.domain_exc import DomainValidationError
from bench.domain.exceptions.handler import (
    handle_exception,
    install_global_handler,
)
from bench.domain.exceptions.logging_exc import LoggingConfigError, SymlinkError

__all__ = [
    "BenchException",
    "ConfigurationMissingFieldError",
    "DatabaseClientError",
    "DomainValidationError",
    "LLMClientError",
    "LoggingConfigError",
    "ModelOutputContractError",
    "ProviderConfigError",
    "SpecDuplicatedError",
    "SymlinkError",
    "handle_exception",
    "install_global_handler",
]
