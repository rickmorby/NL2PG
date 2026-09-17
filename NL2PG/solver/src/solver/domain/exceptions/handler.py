"""Gestore polimorfico delle eccezioni per il solver basato su singledispatch.

:author: Riccardo Morabito
"""

from functools import singledispatch
from logging import getLogger
from sys import exit as sys_exit, modules
from rich.console import Console

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
    SymlinkError,
)

_log = getLogger("solver.exceptions")
_console = Console(stderr=True)


@singledispatch
def handle_exception(exc: BaseException) -> None:
    """Handler predefinito per eccezioni generiche non gestite specificamente."""
    _log.critical("%s: %s", type(exc).__name__, exc)
    _console.print(f"[bold red][ERROR][/bold red] {type(exc).__name__}: {exc}")
    sys_exit(1)


@handle_exception.register(ClingoDependencyError)
def _handle_clingo_dependency_error(exc: ClingoDependencyError) -> None:
    """Handler per assenza della libreria obbligatoria Clingo."""
    _log.critical("Dipendenza obbligatoria mancante: %s", exc.message)
    _console.print(f"[bold red][ERRORE CRITICO CLINGO][/bold red] {exc.message}")
    _console.print(
        "[bold yellow][AZIONE RICHIESTA][/bold yellow] Installare clingo tramite: "
        "`uv add clingo` o verificare i binari di sistema."
    )
    sys_exit(1)


@handle_exception.register(SymlinkError)
def _handle_symlink_error(exc: SymlinkError) -> None:
    """Handler per SymlinkError: segnala il percorso alternativo del file di log."""
    log_path = exc.payload.get("path") if isinstance(exc.payload, dict) else "file dedicato"
    _log.warning("Symlink solver.log non creato. Log registrati su: %s", log_path)


@handle_exception.register(SolverConfigurationError)
def _handle_config_error(exc: SolverConfigurationError) -> None:
    """Handler per errori di configurazione del solver."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(BenchmarkFormatError)
def _handle_benchmark_format_error(exc: BenchmarkFormatError) -> None:
    """Handler per anomalie nel formato del dataset benchmark."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(LLMSolverError)
def _handle_llm_error(exc: LLMSolverError) -> None:
    """Handler per fallimenti o timeout nelle chiamate LLM del solver."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(DocRAGError)
def _handle_doc_rag_error(exc: DocRAGError) -> None:
    """Handler per anomalie del motore vettoriale RAG."""
    _log.warning("Errore RAG: %s", exc.message)
    _console.print(f"[bold yellow][WARNING RAG][/bold yellow] {exc.message}")


@handle_exception.register(DatalogExecutionError)
def _handle_datalog_exec_error(exc: DatalogExecutionError) -> None:
    """Handler per errori di esecuzione Datalog / ASP."""
    _log.warning("Errore Datalog: %s", exc.message)
    _console.print(f"[bold yellow][WARNING DATALOG][/bold yellow] {exc.message}")


@handle_exception.register(SQLTranspilationError)
def _handle_transpilation_error(exc: SQLTranspilationError) -> None:
    """Handler per fallimento trasposizione SQL to Datalog."""
    _log.warning("Errore Transpiler: %s", exc.message)
    _console.print(f"[bold yellow][WARNING TRANSPILER][/bold yellow] {exc.message}")


@handle_exception.register(SandboxSolverError)
def _handle_sandbox_error(exc: SandboxSolverError) -> None:
    """Handler per errori di esecuzione nelle sandbox Postgres/Clingo."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(LoggingConfigError)
def _handle_logging_config_error(exc: LoggingConfigError) -> None:
    """Handler per anomalie nel caricamento della configurazione di logging."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


def _global_excepthook(
    _exc_type: type[BaseException],
    exc_value: BaseException,
    _exc_tb: object,
) -> None:
    """Hook globale assegnato a sys.excepthook."""
    handle_exception(exc_value)


def install_global_handler() -> None:
    """Installa l'handler globale su sys.excepthook."""
    modules["sys"].excepthook = _global_excepthook
