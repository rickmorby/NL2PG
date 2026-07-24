"""Modulo package delle eccezioni personalizzate del benchmark.

:author: Riccardo Morabito
"""

from bench.exception.base import BenchException
from bench.exception.models_exc import FieldAccessError, UnknownFieldError
from bench.exception.logging_exc import LoggingConfigError, SymlinkError
from bench.exception.handler import install_global_handler, register_handler

__all__ = [
    "BenchException",
    "FieldAccessError",
    "UnknownFieldError",
    "LoggingConfigError",
    "SymlinkError",
    "install_global_handler",
    "register_handler",
]
