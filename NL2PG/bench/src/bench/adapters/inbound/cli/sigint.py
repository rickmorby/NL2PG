"""Gestore del segnale SIGINT a due stadi per la CLI.

:author: Riccardo Morabito
"""

from os import _exit as os_exit
from signal import SIGINT, signal

from typer import colors, secho

_INTERRUPT_MSG = "\n[WARNING] Interruzione da tastiera (Ctrl+C). Chiusura in corso..."
_INTERRUPT_LIMIT = 2
_INTERRUPT_EXIT_CODE = 130


class _TwoStageSigintHandler:
    """Gestore del segnale SIGINT a due stadi (graceful e forzato)."""

    def __init__(self) -> None:
        self._count = 0

    def __call__(self, _signum: int, _frame: object) -> None:
        self._count += 1
        if self._count >= _INTERRUPT_LIMIT:
            secho("[WARNING] Seconda interruzione: uscita forzata immediata.", fg=colors.YELLOW)
            os_exit(_INTERRUPT_EXIT_CODE)
        raise KeyboardInterrupt

    @staticmethod
    def install() -> None:
        """Installa SIGINT a 2 stadi: 1. KeyboardInterrupt (graceful), 2. os_exit(130)."""
        signal(SIGINT, _TwoStageSigintHandler())
