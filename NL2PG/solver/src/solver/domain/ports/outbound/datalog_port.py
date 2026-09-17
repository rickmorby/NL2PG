"""Porta outbound astratta per il motore di esecuzione Datalog / Clingo.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from typing import Any


class DatalogPort(ABC):
    """Porta astratta per la validazione ed esecuzione di regole Datalog."""

    @abstractmethod
    def validate_syntax(self, datalog_code: str) -> tuple[bool, str]:
        """Valida la sintassi formale del Datalog. Restituisce (is_valid, error_msg)."""

    @abstractmethod
    def run_datalog(
        self,
        facts_datalog: str,
        rules_datalog: str,
        predicate_name: str = "query",
    ) -> tuple[bool, list[tuple[Any, ...]], str]:
        """Esegue il programma Datalog (fatti + regole) su Clingo.

        Restituisce (success, tuple_risultato, error_message).
        """
