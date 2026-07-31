"""Adattatore outbound per l'invocazione di modelli LLM con failover automatico via liteLLM Router.

:author: Riccardo Morabito
"""

from typing import Any
from litellm import Router
from pydantic import BaseModel, ValidationError

from bench.domain.exceptions import LLMClientError, ModelOutputContractError
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort


class LLMClientAdapter(LLMGeneratorPort):
    """Adattatore per l'invocazione di modelli LLM con failover automatico via liteLLM Router."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Inizializza l'adattatore con la configurazione dei provider e la strategia di routing."""
        self._config = config or {}
        strategy = self._config.get("routing_strategy", "latency-based-routing")
        self._router = Router(
            model_list=self._build_model_list(self._config),
            routing_strategy=strategy,
            num_retries=self._config.get("num_retries", 3),
            cooldown_time=self._config.get("cooldown_time", 60),
            set_verbose=False,
        )

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
        """Chiama la catena LLM guidata dai prompt con failover automatico via liteLLM Router."""
        opts = options or CallOptionsDTO()
        messages = [{"role": "user", "content": prompt}]

        if opts.error_feedback:
            msg = f"ERRORE PRECEDENTE:\n{opts.error_feedback}\n\nCorreggi e riprova."
            messages.append({"role": "user", "content": msg})

        try:
            kwargs: dict[str, Any] = {"model": role, "messages": messages}
            if opts.temperature_override is not None:
                kwargs["temperature"] = opts.temperature_override

            response = self._router.completion(**kwargs)
            msg = response.choices[0].message
            content = (msg.content or "").strip()

            if content.startswith("```"):
                first_nl = content.find("\n")
                if first_nl != -1 and content[:first_nl].strip().lower().startswith("```"):
                    content = content[first_nl + 1:]
                else:
                    content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            cleaned_json = content.strip()

            try:
                output = schema.model_validate_json(cleaned_json)
            except ValidationError as ve:
                msg_err = (
                    f"L'output del modello '{response.model}' non rispetta lo schema "
                    f"'{schema.__name__}': {ve}. Rispondere ESCLUSIVAMENTE con JSON valido."
                )
                payload = {"schema": schema.__name__, "raw": cleaned_json}
                raise ModelOutputContractError(msg_err, payload=payload) from ve

            return CallResultDTO(output=output, model_used=response.model)
        except ModelOutputContractError:
            raise
        except Exception as e:
            raise LLMClientError(f"Catena {role} esaurita: {e}") from e

    def close(self) -> None:
        """Rilascia le risorse di rete ed i pool dei client LLM."""
        if hasattr(self, "_router"):
            self._router = None

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
