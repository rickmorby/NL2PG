"""Porta outbound astratta per la generazione LLM con tool calling.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from typing import Any, Callable


class LLMGeneratorPort(ABC):
    """Porta astratta per l'invocazione degli LLM con supporto a Tool Calling."""

    @abstractmethod
    def call_with_tools(
        self,
        model_role: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], tuple[str, bool]],
        max_iterations: int = 5,
    ) -> tuple[str, list[dict[str, Any]], str]:
        """Esegue il loop agentico di Tool Calling.

        Restituisce (final_response_text, tool_calls_trace, model_used).
        """
