"""Handler personalizzati per il logging del benchmark.

:author: Riccardo Morabito
"""

from logging import Handler
from tqdm import tqdm


class TqdmHandler(Handler):
    """Handler che scrive i log su tqdm.write() per non interferire con le barre di progresso."""

    def emit(self, record: object) -> None:
        """Invia il record formattato a tqdm.write()."""
        tqdm.write(self.format(record))
