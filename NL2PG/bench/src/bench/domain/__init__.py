"""Modulo package principale del nucleo di dominio (Core).

:author: Riccardo Morabito
"""

from bench.domain.exceptions import BenchException
from bench.domain.models import AbstractDTO, TaskStateDTO

__all__ = [
    "BenchException",
    "AbstractDTO",
    "TaskStateDTO",
]
