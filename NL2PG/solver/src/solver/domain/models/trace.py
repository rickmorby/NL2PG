"""DTO per la registrazione dei trace di invocazione strumenti (Tool Calling).

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import Field
from solver.domain.models.base import AbstractDTO


class ToolCallDTO(AbstractDTO):
    """Registrazione di una singola chiamata ad uno strumento."""

    tool_name: str = Field(default="")
    arguments: dict[str, Any] = Field(default_factory=dict)
    output_summary: str = Field(default="")
    step: int = Field(default=1)
    success: bool = Field(default=True)
    error_message: str | None = Field(default=None)


class ToolTraceDTO(AbstractDTO):
    """Tracciamento completo dell'interazione dell'agente con i 5 strumenti."""

    calls: list[ToolCallDTO] = Field(default_factory=list)
    is_one_shot: bool = Field(default=True)

    @property
    def total_calls(self) -> int:
        """Restituisce il numero totale di chiamate a strumenti effettuati."""
        return len(self.calls)

    @property
    def used_tools(self) -> set[str]:
        """Restituisce l'insieme dei nomi dei tool univoci utilizzati."""
        return {c.tool_name for c in self.calls}
