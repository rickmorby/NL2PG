"""Gerarchia di eccezioni del dominio solver.

:author: Riccardo Morabito
"""

from typing import Any


class SolverException(Exception):
    """Eccezione base per tutte le anomalie del solver."""

    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        """Inizializza l'eccezione con messaggio e payload opzionale."""
        super().__init__(message)
        self.message = message
        self.payload = payload or {}


class SolverConfigurationError(SolverException):
    """Sollevata in caso di errori di configurazione del solver."""


class LLMSolverError(SolverException):
    """Sollevata per errori di comunicazione con i provider LLM."""


class SandboxSolverError(SolverException):
    """Sollevata per fallimenti nell'esecuzione delle sandbox (Postgres/Clingo)."""


class ClingoDependencyError(SandboxSolverError):
    """Sollevata quando la libreria nativa 'clingo' non e' installata nell'ambiente."""


class DatalogExecutionError(SandboxSolverError):
    """Sollevata per errori di grounding o risoluzione dei modelli ASP Clingo."""


class DocRAGError(SolverException):
    """Sollevata per anomalie durante l'indicizzazione o la ricerca vettoriale RAG."""


class SQLTranspilationError(SolverException):
    """Sollevata quando la trasposizione da SQL a Datalog fallisce."""


class BenchmarkFormatError(SolverException):
    """Sollevata se il file benchmark di input non e' nel formato atteso."""


class LoggingConfigError(SolverException):
    """Sollevata se la configurazione del logging e' assente o non valida."""


class SymlinkError(SolverException):
    """Sollevata se la creazione del symlink solver.log fallisce."""
