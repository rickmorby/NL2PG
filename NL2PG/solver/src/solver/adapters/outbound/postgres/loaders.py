"""Loader psycopg3 per la conversione dei tipi PostgreSQL in tipi Python JSON-safe.

:author: Riccardo Morabito
"""

from decimal import Decimal
from psycopg import adapters
from psycopg.adapt import Loader


class JsonSafeNumericLoader(Loader):
    """Converte i valori PostgreSQL numeric in int o float nativo."""

    def load(self, data: memoryview) -> int | float:
        """Decodifica il valore numerico ed esporta tipo JSON-safe."""
        value = Decimal(data.tobytes().decode("utf-8"))
        return int(value) if value == int(value) else float(value)


class JsonSafeIntervalLoader(Loader):
    """Converte i valori PostgreSQL interval in stringa."""

    def load(self, data: memoryview) -> str:
        """Decodifica l'intervallo come testo."""
        return data.tobytes().decode("utf-8")


class JsonSafeByteaLoader(Loader):
    """Converte i valori PostgreSQL bytea in stringa UTF-8."""

    def load(self, data: memoryview) -> str:
        """Decodifica il contenuto binario."""
        return data.tobytes().decode("utf-8", errors="replace")


class JsonSafeLoadersRegistry:
    """Registry di utilità per la configurazione dei loader JSON-safe in psycopg."""

    @staticmethod
    def register() -> None:
        """Registra globalmente i loader JSON-safe nel template psycopg."""
        adapters.register_loader("numeric", JsonSafeNumericLoader)
        adapters.register_loader("interval", JsonSafeIntervalLoader)
        adapters.register_loader("bytea", JsonSafeByteaLoader)


register_json_safe_loaders = JsonSafeLoadersRegistry.register
