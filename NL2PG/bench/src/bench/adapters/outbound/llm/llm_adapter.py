"""Adattatore outbound per l'invocazione di modelli LLM con failover automatico via liteLLM Router.

:author: Riccardo Morabito
"""

from logging import getLogger
from typing import Any
from litellm import Router
from pydantic import BaseModel
from bench.domain.exceptions import LLMClientError
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort

_log = getLogger("bench.adapters.llm")


class LLMClientAdapter(LLMGeneratorPort):
    """Adattatore per l'invocazione di modelli LLM con failover automatico via liteLLM Router."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Inizializza l'adattatore con la configurazione dei provider."""
        self._config = config or {}
        self._router = Router(model_list=self._build_model_list(self._config))

    def get_config(self) -> dict[str, Any]:
        """Restituisce il dizionario di configurazione dell'adattatore."""
        return self._config

    def get_chain(self, role: str) -> list[str]:
        """Restituisce la lista dei model_id per un ruolo dalla configurazione."""
        chains = self._config.get("chains", {})
        return list(chains.get(role, []))

    def call_model(
        self,
        role: str,
        prompt: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> CallResultDTO:
        """Chiama la catena LLM con failover automatico gestito da liteLLM Router."""
        opts = options or CallOptionsDTO()
        messages = [{"role": "user", "content": prompt}]

        if opts.error_feedback:
            msg = f"ERRORE PRECEDENTE:\n{opts.error_feedback}\n\nCorreggi e riprova."
            messages.append({"role": "user", "content": msg})

        try:
            response = self._router.completion(
                model=role,
                messages=messages,
                response_format=schema,
            )
            msg = response.choices[0].message
            output = (
                msg.parsed
                if (hasattr(msg, "parsed") and msg.parsed is not None)
                else schema.model_validate_json(msg.content)
            )
            return CallResultDTO(output=output, model_used=response.model)
        except Exception as e:
            raise LLMClientError(f"Catena {role} esaurita: {e}") from e

    @staticmethod
    def _build_model_list(config: dict[str, Any]) -> list[dict[str, Any]]:
        """Costruisce la model_list per liteLLM Router dalla configurazione providers.json."""
        model_list: list[dict[str, Any]] = []
        models = config.get("models", {})
        chains = config.get("chains", {})

        for role, model_ids in chains.items():
            for mid in model_ids:
                mc = models.get(mid)
                if not mc:
                    continue
                entry = {
                    "model_name": role,
                    "litellm_params": {
                        "model": f"{mc['provider']}/{mc['model']}",
                        "api_key": mc["api_key"],
                        "max_tokens": mc["max_tokens"],
                        "temperature": mc["temperature"],
                        "timeout": mc.get("request_timeout", 120),
                        "rpm": 100,
                    },
                }
                if "base_url" in mc:
                    entry["litellm_params"]["api_base"] = mc["base_url"]
                model_list.append(entry)

        return model_list