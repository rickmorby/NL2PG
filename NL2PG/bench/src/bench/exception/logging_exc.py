"""Modulo delle eccezioni relative al logger.

:author: Riccardo Morabito
"""

from bench.exception.base import BenchException


class LoggingConfigError(BenchException):
    """Errore sollevato quando il file di configurazione del logging è assente."""


class SymlinkError(BenchException):
    """Errore sollevato quando la creazione del symlink bench.log fallisce."""
