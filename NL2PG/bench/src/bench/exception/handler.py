"""Modulo per la gestione globale delle eccezioni del benchmark.

:author: Riccardo Morabito
"""

from sys import excepthook, stderr, exit as sys_exit, modules

RED = "\033[91m"
RESET = "\033[0m"

_excepthook_original = excepthook


def _global_handler(exc_type: type, exc_value: BaseException, exc_tb: object) -> None:
    """Handler globale per qualsiasi eccezione non catturata."""
    print(f"{RED}[ERROR]: {exc_value}{RESET}", file=stderr)
    sys_exit(1)


def install_global_handler() -> None:
    """Installa l'handler globale per le eccezioni non catturate."""
    modules["sys"].excepthook = _global_handler
