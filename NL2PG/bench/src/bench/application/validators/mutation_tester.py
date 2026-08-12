"""Modulo validatore applicativo per il mutation testing su query SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass

from bench.domain.ports.outbound.sandbox_port import SandboxPort


@dataclass
class MutationResult:
    """Esito del test di mutazione su una query SQL."""

    is_valid: bool = True
    error: str = ""


class MutationTester:
    """Validatore applicativo che coordina la verifica di sensibilita' a mutazioni dei dati."""

    def __init__(self, sandbox: SandboxPort):
        """Inietta la porta sandbox per l'esecuzione dei test di mutazione."""
        self._sandbox = sandbox

    def test(self, schema: str, query: str, tables: list[str], attempts: int = 3) -> MutationResult:
        """Testa se la query e' sensibile a mutazioni dei dati nello schema sandbox."""
        ok, err = self._sandbox.test_data_mutation(schema, query, tables, attempts)
        return MutationResult(is_valid=ok, error=err)
