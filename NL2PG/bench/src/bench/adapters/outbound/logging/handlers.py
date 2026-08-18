"""Modulo contenente gli handler personalizzati per il logging.

:author: Riccardo Morabito
"""

from logging import Handler, LogRecord
from tqdm import tqdm


class TqdmHandler(Handler):
    """Handler di logging che invia i messaggi a tqdm.write per le barre di progresso."""

    def emit(self, record: LogRecord) -> None:
        """Emette il record di log formattato tramite tqdm.write."""
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except (RecursionError, ValueError, TypeError, OSError, RuntimeError):
            self.handleError(record)
