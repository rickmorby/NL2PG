"""Servizio di dominio puro per la classificazione automatica degli errori.

:author: Riccardo Morabito
"""

from typing import Any

from solver.domain.models.error import ErrorType
from solver.domain.services.validation import ResultComparator


class ErrorClassifier:
    """Classifica messaggi di errore da Postgres, Clingo o comparazione risultati."""

    def __init__(self) -> None:
        """Inizializza il comparatore interno per la diagnostica delle discrepanze."""
        self._comparator = ResultComparator()

    def classify_postgres_error(self, err_msg: str) -> ErrorType:
        """Classifica le eccezioni restituite da PostgreSQL."""
        msg = err_msg.lower()
        if "relation" in msg and "does not exist" in msg:
            return ErrorType.TABLE_NOT_FOUND
        if "column" in msg and "does not exist" in msg:
            return ErrorType.COLUMN_NOT_FOUND
        if "ambiguous" in msg:
            return ErrorType.AMBIGUOUS_COLUMN
        if any(k in msg for k in ("type", "cannot cast", "datatype mismatch")):
            return ErrorType.TYPE_MISMATCH
        if any(k in msg for k in ("syntax error", "parse error", "group by")):
            return ErrorType.SYNTAX_ERROR
        return ErrorType.UNKNOWN_ERROR

    def classify_clingo_error(self, err_msg: str) -> ErrorType:
        """Classifica le eccezioni o i warning restituiti dal solver Clingo."""
        msg = err_msg.lower()
        if "unsafe" in msg or "unbound" in msg:
            return ErrorType.UNBOUND_VAR
        if any(k in msg for k in ("syntax error", "parsing failed", "lexer error")):
            return ErrorType.SYNTAX_ERROR
        if "undefined predicate" in msg or "unknown predicate" in msg:
            return ErrorType.TABLE_NOT_FOUND
        return ErrorType.UNKNOWN_ERROR

    def classify_result_mismatch(
        self,
        candidate_rows: list[list[Any]] | list[tuple[Any, ...]],
        gold_rows: list[list[Any]],
        order_sensitive: bool,
    ) -> ErrorType:
        """Classifica la discrepanza tra il risultato del candidato e quello gold."""
        if len(candidate_rows) != len(gold_rows):
            return ErrorType.WRONG_ROW_COUNT

        is_multiset_match = self._comparator.compare(
            candidate_rows, gold_rows, order_sensitive=False
        )
        if order_sensitive and is_multiset_match:
            return ErrorType.WRONG_ORDERING

        return ErrorType.WRONG_VALUES
