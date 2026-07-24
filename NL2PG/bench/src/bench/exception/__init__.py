"""Modulo package delle eccezioni personalizzate del benchmark.

:author: Riccardo Morabito
"""

from bench.exception.base import BenchException
from bench.exception.models_exc import FieldAccessError, UnknownFieldError
from bench.exception.handler import install_global_handler

__all__ = [
    "BenchException",
    "FieldAccessError",
    "UnknownFieldError",
    "install_global_handler",
]
