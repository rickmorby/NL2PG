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

    def few_shot(self, category_id: str) -> str:
        """Carica fino a 3 esempi JSON/YAML da examples/{category_id}/ separati da ---."""
        examples_dir = self._dir.parent / "examples" / category_id
        if not examples_dir.exists():
            return ""
        files = sorted(
            list(examples_dir.glob("*.json")) + list(examples_dir.glob("*.yaml"))
        )[:3]
        parts = [f.read_text(encoding="utf-8") for f in files]
        return "\n---\n".join(parts)
