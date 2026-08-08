"""Modulo package degli adattatori di serializzazione outbound.

:author: Riccardo Morabito
"""

from bench.adapters.outbound.serializer.json_serializer_adapter import (
    JsonBenchmarkSerializerAdapter,
)

__all__ = ["JsonBenchmarkSerializerAdapter"]
