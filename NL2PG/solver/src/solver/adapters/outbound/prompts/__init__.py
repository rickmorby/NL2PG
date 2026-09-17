"""Adapter per il caricamento dei template prompt da filesystem per il solver.

:author: Riccardo Morabito
"""

from pathlib import Path

from solver.domain.ports.outbound.prompt_port import PromptPort


class PromptAdapter(PromptPort):
    """Carica template prompt da file .txt e li formatta con i kwargs forniti."""

    def __init__(self, prompts_dir: Path) -> None:
        """Salva il percorso della directory dei template prompt."""
        self._dir = prompts_dir

    def load(self, name: str, **kwargs: object) -> str:
        """Carica il template {name}.txt e sostituisce i placeholder {key} con i kwargs."""
        path = self._dir / f"{name}.txt"
        if not path.exists():
            return f"Template prompt '{name}' non trovato."
        template = path.read_text(encoding="utf-8")
        for key, val in kwargs.items():
            template = template.replace(f"{{{key}}}", str(val))
        return template
