"""Adapter per caricamento template prompt da filesystem.

:author: Riccardo Morabito
"""

from pathlib import Path

from bench.domain.ports.outbound.prompt_port import PromptPort


class PromptAdapter(PromptPort):
    """Carica template prompt da file .txt e li formatta con i kwargs forniti."""

    def __init__(self, prompts_dir: Path) -> None:
        """Salva il percorso della directory dei template prompt."""
        self._dir = prompts_dir

    def load(self, name: str, **kwargs: object) -> str:
        """Carica il template {name}.txt e sostituisce i placeholder {key} con i kwargs."""
        template = (self._dir / f"{name}.txt").read_text(encoding="utf-8")
        for key, val in kwargs.items():
            template = template.replace(f"{{{key}}}", str(val))
        return template
