"""Loader psycopg3 per la conversione dei tipi PostgreSQL in tipi Python JSON-safe.

Il registro globale ``psycopg.adapters`` e' il template di adattamento usato da ogni
nuova connessione: registrando i loader qui, la conversione avviene una sola volta,
alla frontiera del database, e il dominio vede esclusivamente tipi primitivi Python
che ``orjson`` serializza nativamente.

:author: Riccardo Morabito
"""

from decimal import Decimal

from psycopg import adapters
from psycopg.adapt import Loader


class JsonSafeNumericLoader(Loader):
    """Converte i valori PostgreSQL ``numeric`` in ``int`` o ``float`` nativo.

    I valori interi restano ``int`` (senza perdita di precisione ne' suffisso ``.0``);
    i valori con parte frazionaria diventano ``float``.
    """

    def load(self, data: memoryview) -> int | float:
        """Decodifica il valore numerico esatto e lo riduce a tipo JSON-safe."""
        value = Decimal(data.tobytes().decode("utf-8"))
        return int(value) if value == int(value) else float(value)


class JsonSafeIntervalLoader(Loader):
    """Converte i valori PostgreSQL ``interval`` in stringa (``timedelta`` non e' JSON-safe)."""

    def load(self, data: memoryview) -> str:
        """Decodifica l'intervallo e lo restituisce in forma testuale."""
        return data.tobytes().decode("utf-8")


class JsonSafeByteaLoader(Loader):
    """Converte i valori PostgreSQL ``bytea`` in stringa UTF-8 (``bytes`` non e' JSON-safe)."""

    def load(self, data: memoryview) -> str:
        """Decodifica il contenuto binario come testo UTF-8."""
        return data.tobytes().decode("utf-8", errors="replace")


class JsonSafeLoadersRegistry:
    """Registry di utilità per la configurazione dei loader JSON-safe in psycopg."""

    @staticmethod
    def register() -> None:
        """Registra globalmente i loader JSON-safe nel template delle connessioni psycopg."""
        adapters.register_loader("numeric", JsonSafeNumericLoader)
        adapters.register_loader("interval", JsonSafeIntervalLoader)
        adapters.register_loader("bytea", JsonSafeByteaLoader)
