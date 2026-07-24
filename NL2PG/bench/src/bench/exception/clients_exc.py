"""Modulo delle eccezioni relative ai client di infrastruttura.

:author: Riccardo Morabito
"""

from bench.exception.base import BenchException


class DatabaseClientError(BenchException):
    """Errore sollevato durante le operazioni sul database PostgreSQL."""
