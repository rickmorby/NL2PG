"""Modulo delle eccezioni relative al layer models.

:author: Riccardo Morabito
"""

from bench.exception.base import BenchException


class FieldAccessError(BenchException):
    """Accesso diretto a un campo privato senza utilizzare il getter."""


class UnknownFieldError(BenchException):
    """Accesso a un attributo inesistente sul DTO."""
