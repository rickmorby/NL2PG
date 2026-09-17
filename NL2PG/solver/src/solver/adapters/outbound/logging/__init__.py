"""Package per gli adattatori di logging del solver.

:author: Riccardo Morabito
"""

from solver.adapters.outbound.logging.handlers import TqdmHandler
from solver.adapters.outbound.logging.logger_adapter import LoggingAdapter

__all__ = ["LoggingAdapter", "TqdmHandler"]
