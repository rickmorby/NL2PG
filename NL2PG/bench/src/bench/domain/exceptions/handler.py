"""Modulo per la gestione globale delle eccezioni del benchmark basato su singledispatch.

:author: Riccardo Morabito
"""

from functools import singledispatch
from logging import getLogger
from sys import exit as sys_exit, modules
from rich.console import Console
from bench.domain.exceptions.logging_exc import SymlinkError

_log = getLogger("bench.domain.exceptions")
_console = Console(stderr=True)


@singledispatch
def handle_exception(exc: BaseException) -> None:
    """Handler predefinito per eccezioni generiche non gestite specificamente."""
    _log.critical("%s: %s", type(exc).__name__, exc)
    _console.print(f"[bold red][ERROR][/bold red] {type(exc).__name__}: {exc}")
    sys_exit(1)


@handle_exception.register(SymlinkError)
def _handle_symlink_error(exc: SymlinkError) -> None:
    """Handler per SymlinkError: i log sono registrati sul file dedicato."""
    log_path = getattr(exc, "payload", None) or "file dedicato"
    _log.warning("Symlink bench.log non creato. I log sono comunque registrati su: %s", log_path)


def _global_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: object,
) -> None:
    """Hook globale assegnato a sys.excepthook che delega il dispatch a handle_exception."""
    handle_exception(exc_value)


def install_global_handler() -> None:
    """Installa l'handler globale su sys.excepthook."""
    modules["sys"].excepthook = _global_excepthook
