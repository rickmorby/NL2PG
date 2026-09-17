"""Package per la gestione delle eccezioni di dominio del solver.

:author: Riccardo Morabito
"""

from solver.domain.exceptions.base import (
    BenchmarkFormatError,
    ClingoDependencyError,
    DatalogExecutionError,
    DocRAGError,
    LLMSolverError,
    LoggingConfigError,
    SQLTranspilationError,
    SandboxSolverError,
    SolverConfigurationError,
    SolverException,
    SymlinkError,
)
from solver.domain.exceptions.handler import handle_exception, install_global_handler

__all__ = [
    "BenchmarkFormatError",
    "ClingoDependencyError",
    "DatalogExecutionError",
    "DocRAGError",
    "LLMSolverError",
    "LoggingConfigError",
    "SQLTranspilationError",
    "SandboxSolverError",
    "SolverConfigurationError",
    "SolverException",
    "SymlinkError",
    "handle_exception",
    "install_global_handler",
]
