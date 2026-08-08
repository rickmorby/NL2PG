"""Modulo di compatibilità per l'adattatore di serializzazione benchmark.

:author: Riccardo Morabito
"""

from bench.adapters.outbound.serializer.json_serializer_adapter import (
    JsonBenchmarkSerializerAdapter as BenchmarkSerializer,
)

__all__ = ["BenchmarkSerializer"]
