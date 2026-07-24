"""Modulo per la gestione globale delle eccezioni del benchmark.

:author: Riccardo Morabito
"""

from logging import getLogger
from sys import excepthook, stderr, exit as sys_exit, modules
from bench.exception.logging_exc import SymlinkError

RED = "\033[91m"
RESET = "\033[0m"

_log = getLogger("bench.exception")
_excepthook_original = excepthook

_handler_registry: dict[type, callable] = {}


def register_handler(exc_type: type, handler_func: callable) -> None:
    """Registra un handler personalizzato per un tipo di eccezione."""
    _handler_registry[exc_type] = handler_func


def _global_handler(exc_type: type, exc_value: BaseException, exc_tb: object) -> None:
    """Handler globale per qualsiasi eccezione non catturata."""
    handler = _handler_registry.get(exc_type)
    if handler is not None:
        handler(exc_type, exc_value, exc_tb)
        return

    _log.critical("%s: %s", type(exc_value).__name__, exc_value)
    print(f"{RED}[ERROR]: {exc_value}{RESET}", file=stderr)
    sys_exit(1)


def install_global_handler() -> None:
    """Installa l'handler globale e registra gli handler predefiniti."""
    _handler_registry.clear()
    _handler_registry[SymlinkError] = _handle_symlink_error
    modules["sys"].excepthook = _global_handler


def _handle_symlink_error(exc_type: type, exc_value: BaseException, exc_tb: object) -> None:
    """Handler per SymlinkError: il symlink non è essenziale, i log sono sul file dedicato."""
    log_path = getattr(exc_value, "payload", None) or "file dedicato"
    _log.warning("Symlink bench.log non creato. I log sono comunque registrati su: %s", log_path)
