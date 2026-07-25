"""Porta astratta outbound per la validazione dello schema fisico del database.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class DatabaseSchemaValidatorPort(ABC):
    """Porta outbound per la validazione dello schema fisico del database all'avvio."""

    @abstractmethod
    def validate_meta_schema(self) -> None:
        """Verifica la presenza e la conformità dello schema bench_meta e delle sue tabelle."""
        pass
