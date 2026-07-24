"""Modulo package delle eccezioni personalizzate del benchmark.

:author: Riccardo Morabito
"""

from bench.exception.base import BenchException
from bench.exception.clients_exc import DatabaseClientError
from bench.exception.handler import (
    handle_exception,
    install_global_handler,
)
from bench.exception.logging_exc import LoggingConfigError, SymlinkError
from bench.exception.models_exc import FieldAccessError, UnknownFieldError

__all__ = [
    "BenchException",
    "DatabaseClientError",
    "FieldAccessError",
    "LoggingConfigError",
    "SymlinkError",
    "UnknownFieldError",
    "handle_exception",
    "install_global_handler",
]

