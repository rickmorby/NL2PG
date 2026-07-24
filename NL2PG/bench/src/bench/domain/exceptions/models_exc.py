"""Modulo delle eccezioni per l'accesso e la manipolazione dei DTO.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException


class FieldAccessError(BenchException):
    """Sollevata quando si tenta di accedere direttamente a un campo privato DTO senza usare il getter."""


class UnknownFieldError(BenchException):
    """Sollevata quando si richiede un attributo non esistente nel DTO."""
