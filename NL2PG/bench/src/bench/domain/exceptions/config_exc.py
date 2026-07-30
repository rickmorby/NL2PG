"""Modulo delle eccezioni relative alla configurazione del benchmark.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException


class ConfigurationMissingFieldError(BenchException):
    """Sollevata quando un campo o file di configurazione è assente."""
