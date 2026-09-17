"""Tassonomia unificata degli errori di esecuzione e di sintassi per SQL e Datalog.

:author: Riccardo Morabito
"""

from enum import Enum


class ErrorType(str, Enum):
    """Tipi di errori catalogati dal solver durante l'esecuzione."""

    SYNTAX_ERROR = "SYNTAX_ERROR"
    UNBOUND_VAR = "UNBOUND_VAR"
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    AMBIGUOUS_COLUMN = "AMBIGUOUS_COLUMN"
    WRONG_ROW_COUNT = "WRONG_ROW_COUNT"
    WRONG_VALUES = "WRONG_VALUES"
    WRONG_ORDERING = "WRONG_ORDERING"
    DUPLICATE_ROWS = "DUPLICATE_ROWS"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    REPAIR_LOOP_EXHAUSTED = "REPAIR_LOOP_EXHAUSTED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
