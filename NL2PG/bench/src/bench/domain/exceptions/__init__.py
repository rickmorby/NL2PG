"""Modulo package delle eccezioni personalizzate del benchmark.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException
from bench.domain.exceptions.clients_exc import (
    DatabaseClientError,
    LLMClientError,
    ProviderConfigError,
)
from bench.domain.exceptions.handler import (
    handle_exception,
    install_global_handler,
)
from bench.domain.exceptions.logging_exc import LoggingConfigError, SymlinkError


__all__ = [
    "BenchException",
    "DatabaseClientError",
    "LLMClientError",
    "ProviderConfigError",
    "LoggingConfigError",
    "SymlinkError",
    "handle_exception",
    "install_global_handler",
]
