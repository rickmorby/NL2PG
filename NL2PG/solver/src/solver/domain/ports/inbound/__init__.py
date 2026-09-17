"""Modulo package per le porte inbound del solver.

:author: Riccardo Morabito
"""

from solver.domain.ports.inbound.analytics_port import SolverAnalyticsPort
from solver.domain.ports.inbound.solver_runner_port import SolverRunnerPort

__all__ = [
    "SolverAnalyticsPort",
    "SolverRunnerPort",
]
