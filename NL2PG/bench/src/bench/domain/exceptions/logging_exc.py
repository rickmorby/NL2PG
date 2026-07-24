"""Modulo delle eccezioni relative alla configurazione del logging.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException


class LoggingConfigError(BenchException):
    """Sollevata quando il file di configurazione del logging è assente o non valido."""


class SymlinkError(BenchException):
    """Sollevata quando la creazione o l'aggiornamento del symlink bench.log fallisce."""
