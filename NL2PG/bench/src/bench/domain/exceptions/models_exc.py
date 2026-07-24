"""Modulo delle eccezioni per l'accesso e la manipolazione dei DTO.

:author: Riccardo Morabito
"""

from bench.domain.exceptions.base import BenchException


class FieldAccessError(BenchException):
    """Sollevata quando si tenta di accedere a un campo privato DTO senza getter."""


class UnknownFieldError(BenchException):
    """Sollevata quando si richiede un attributo non esistente nel DTO."""
