"""Adattatore outbound per l'invocazione di modelli LLM con failover automatico via liteLLM Router.

:author: Riccardo Morabito
"""

from asyncio import all_tasks, gather, get_event_loop
from contextlib import suppress
from logging import getLogger
from sys import modules
from typing import Any

from json_repair import repair_json
from litellm import (
    Router,
    close_litellm_async_clients,
    in_memory_llm_clients_cache,
)
from pydantic import BaseModel, ValidationError

from bench.adapters.outbound.llm.llm_health_checker_adapter import (
    LLMHealthCheckerAdapter,
)
from bench.domain.exceptions import LLMClientError, ModelOutputContractError
from bench.domain.models.llm import (
    CallOptionsDTO,
    CallResultDTO,
    SystemHealthReportDTO,
)
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort

_log = getLogger("bench.adapters.llm")

modules["litellm"].suppress_debug_info = True
modules["litellm"].turn_off_message_logging = True


class LLMClientAdapter(LLMGeneratorPort):
    """Adattatore per l'invocazione di modelli LLM con failover automatico via liteLLM Router."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        health_checker: LLMHealthCheckerAdapter | None = None,
    ):
        """Inizializza l'adattatore con la configurazione dei provider e i fallback."""
        self._config = config or {}
        self._health_checker = health_checker or LLMHealthCheckerAdapter(self._config)
        strategy = self._config.get("routing_strategy", "simple-shuffle")
        retry_cfg = self._config.get("retry", {})
        num_retries = retry_cfg.get("num_retries", 0)
        cooldown_time = retry_cfg.get("cooldown_time_seconds", 15)
        allowed_fails = retry_cfg.get("allowed_fails", 1)

        self._router = Router(
            model_list=self._build_model_list(self._config),
            fallbacks=self._build_fallbacks(self._config),
            routing_strategy=strategy,
            num_retries=num_retries,
            cooldown_time=cooldown_time,
            allowed_fails=allowed_fails,
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
            content = getattr(msg, "content", None) or ""

            cleaned_json = _extract_json_payload(content)

            if not cleaned_json:
                msg_err = (
                    f"L'output del modello '{response.model}' è vuoto. "
                    "Il modello potrebbe aver esaurito i token nel ragionamento CoT. "
                    "Rispondere ESCLUSIVAMENTE con JSON valido."
                )
                payload = {"schema": schema.__name__, "raw": ""}
                raise ModelOutputContractError(msg_err, payload=payload)

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

    def check_all_providers(self, check_models: bool = True) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello dei provider e dei modelli fisici univoci."""
        return self._health_checker.check_all_providers(check_models=check_models)

    def close(self) -> None:
        """Rilascia le risorse di rete, i pool ed i meccanismi di cache dei client LLM."""
        if self._router is not None:
            with suppress(Exception):
                self._router.reset()
            self._router = None

        with suppress(Exception):
            if callable(close_litellm_async_clients):
                with suppress(Exception):
                    loop = get_event_loop()
                    if not loop.is_closed():
                        pending = [t for t in all_tasks(loop) if not t.done()]
                        for task in pending:
                            task.cancel()
                        if not loop.is_running() and pending:
                            loop.run_until_complete(gather(*pending, return_exceptions=True))
                        if loop.is_running():
                            self._async_close_task = loop.create_task(close_litellm_async_clients())
                        else:
                            loop.run_until_complete(close_litellm_async_clients())
            if isinstance(in_memory_llm_clients_cache, dict):
                in_memory_llm_clients_cache.clear()

    @classmethod
    def _build_model_list(cls, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Costruisce la model_list per liteLLM Router con identificativi univoci."""
        model_list: list[dict[str, Any]] = []
        models = config.get("models", {})
        chains = config.get("chains", {})
        registered_keys: set[tuple[str, str]] = set()

        for role, mid_list in chains.items():
            if not mid_list:
                continue

            for idx, mid in enumerate(mid_list):
                mc = models.get(mid)
                model_key = role if idx == 0 else mid
                if mc and (model_key, mid) not in registered_keys:
                    params = cls._make_litellm_params(mc)
                    model_list.append({"model_name": model_key, "litellm_params": params})
                    registered_keys.add((model_key, mid))

        return model_list

    @staticmethod
    def _make_litellm_params(mc: dict[str, Any]) -> dict[str, Any]:
        """Costruisce il dizionario dei parametri litellm_params per una configurazione modello."""
        params: dict[str, Any] = {
            "model": f"{mc['provider']}/{mc['model']}",
            "api_key": mc["api_key"],
            "temperature": mc["temperature"],
            "timeout": mc.get("request_timeout", 120),
            "rpm": 100,
        }
        if "max_tokens" in mc:
            params["max_tokens"] = mc["max_tokens"]
        if "base_url" in mc:
            params["api_base"] = mc["base_url"]
        return params

    @staticmethod
    def _build_fallbacks(config: dict[str, Any]) -> list[dict[str, list[str]]]:
        """Costruisce la lista di fallback deterministici tra provider per ciascun ruolo."""
        fallbacks: list[dict[str, list[str]]] = []
        chains = config.get("chains", {})
        for role, mid_list in chains.items():
            if len(mid_list) > 1:
                fallbacks.append({role: mid_list[1:]})
                for idx, mid in enumerate(mid_list):
                    if idx < len(mid_list) - 1:
                        fallbacks.append({mid: mid_list[idx + 1 :]})
        return fallbacks


def _extract_json_payload(text: str) -> str:
    """Estrae l'oggetto JSON finale da un testo LLM scartando CoT e riparando la sintassi."""
    return repair_json(text.strip(), ensure_ascii=False) if text else ""
