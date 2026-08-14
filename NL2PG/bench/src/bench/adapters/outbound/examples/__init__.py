"""Adapter per il caricamento degli esempi few-shot role-specific da filesystem.

:author: Riccardo Morabito
"""

from pathlib import Path

from orjson import loads as orjson_loads

from bench.domain.ports.outbound.example_port import ExamplePort


class ExampleAdapter(ExamplePort):
    """Carica fino a 3 esempi JSON da examples/<categoria>/<ruolo>/ come dict Python.

    Puro I/O: non conosce i campi degli esempi; la proiezione ruolo->campi è
    responsabilità del dominio (RoleExampleBuilder) a monte, in promozione.
    """

    def __init__(self, examples_dir: Path) -> None:
        """Salva il percorso della directory radice degli esempi."""
        self._dir = examples_dir

    def load(self, category_id: str, role: str) -> list[dict]:
        """Restituisce fino a 3 esempi JSON come dict, o lista vuota se assenti."""
        role_dir = self._dir / category_id / role
        if not role_dir.exists():
            return []
        files = sorted(role_dir.glob("*.json"))[:3]
        return [orjson_loads(f.read_bytes()) for f in files]
