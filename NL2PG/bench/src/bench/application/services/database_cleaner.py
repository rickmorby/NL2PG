"""Servizio applicativo per la pulizia degli schemi temporanei orfani nel database sandbox.

:author: Riccardo Morabito
"""

from logging import getLogger

from bench.domain.ports.outbound.sandbox_port import SandboxPort

_log = getLogger("bench.application.database_cleaner")


class DatabaseCleanupService:
    """Servizio applicativo che coordina la pulizia degli schemi orfani."""

    def __init__(self, sandbox: SandboxPort) -> None:
        """Inietta la porta sandbox per l'accesso alle operazioni amministrative."""
        self._sandbox = sandbox

    def cleanup_sandbox_schemas(self) -> list[str]:
        """Elimina gli schemi temporanei orfani task_* e ne restituisce l'elenco."""
        removed = self._sandbox.cleanup_orphan_schemas()
        _log.info("Pulizia sandbox completata: %d schemi rimossi.", len(removed))
        return removed
