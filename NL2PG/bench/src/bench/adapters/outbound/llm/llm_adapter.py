"""Adattatore outbound per l'invocazione di modelli LLM con failover automatico via liteLLM Router.

:author: Riccardo Morabito
"""

import json
import time
from asyncio import get_event_loop
from contextlib import suppress
from logging import CRITICAL as LOG_CRITICAL, getLogger
from sys import modules
from typing import Any

from httpx import HTTPError
from json_repair import repair_json
from litellm import (
    Router,
    close_litellm_async_clients,
    in_memory_llm_clients_cache,
    stream_chunk_builder,
)
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadRequestError,
    ContextWindowExceededError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    UnprocessableEntityError,
)
from litellm.types.router import RouterRateLimitError
from openai import OpenAIError
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

getLogger("LiteLLM").setLevel(LOG_CRITICAL)
getLogger("LiteLLM Router").setLevel(LOG_CRITICAL)
getLogger("LiteLLM Proxy").setLevel(LOG_CRITICAL)

litellm_mod = modules["litellm"]
litellm_mod.suppress_debug_info = True
litellm_mod.turn_off_message_logging = True
litellm_mod.set_verbose = False

_LITELLM_PROVIDER_EXCEPTIONS = (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadRequestError,
    ContextWindowExceededError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    UnprocessableEntityError,
    RouterRateLimitError,
    OpenAIError,
    HTTPError,
    OSError,
    ValueError,
    RuntimeError,
)
litellm_mod.callbacks = []
litellm_mod.success_callback = []
litellm_mod.failure_callback = []
litellm_mod.input_callback = []
litellm_mod.service_callback = []
litellm_mod.telemetry = False
litellm_mod.cache = None

for _cb_attr in ("_async_success_callback", "_async_failure_callback", "_async_input_callback"):
    if hasattr(litellm_mod, _cb_attr):
        setattr(litellm_mod, _cb_attr, [])


class LLMClientAdapter(LLMGeneratorPort):
    """Adattatore per l'invocazione di modelli LLM con failover automatico via liteLLM Router."""

    @staticmethod
    def _extract_json_payload(text: str) -> str:
        """Estrae l'oggetto JSON finale da un testo LLM scartando CoT e riparando la sintassi."""
        if not text:
            return ""
        repaired = repair_json(text.strip(), ensure_ascii=False)
        try:
            parsed = json.loads(repaired)
        except (json.JSONDecodeError, ValueError):
            return repaired
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            return json.dumps(parsed[0], ensure_ascii=False)
        return repaired

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
        cooldown_time = retry_cfg.get("cooldown_time_seconds", 0)
        allowed_fails = retry_cfg.get("allowed_fails", 999999)
        optional_pre_call_checks = self._config.get(
            "optional_pre_call_checks", ["enforce_model_rate_limits"]
        )
        self._stream_timeout = retry_cfg.get("stream_timeout", 60)
        self._max_call_seconds = float(retry_cfg.get("max_call_seconds", 240))

        model_list = self._build_model_list(self._config)
        fallbacks = self._build_fallbacks(self._config)
        max_fallbacks = (
            max(
                (len(chain) for chain in self._config.get("chains", {}).values()),
                default=1,
            )
            - 1
        )

        self._router = Router(
            model_list=model_list,
            fallbacks=fallbacks,
            max_fallbacks=max_fallbacks,
            routing_strategy=strategy,
            num_retries=num_retries,
            cooldown_time=cooldown_time,
            allowed_fails=allowed_fails,
            optional_pre_call_checks=optional_pre_call_checks,
            stream_timeout=self._stream_timeout,
            set_verbose=False,
            cache_responses=False,
        )

    def get_chain(self, role: str) -> list[str]:
        """Restituisce la lista dei model_id per un ruolo dalla configurazione."""
        chains = self._config.get("chains", {})
        return list(chains.get(role, []))

    def _primary_model_group(self, role: str) -> str:
        """Risolve il ruolo nel model group del primo modello della catena."""
        models = self._config.get("models", {})
        for model_id in self.get_chain(role):
            if model_id in models:
                return model_id
        return role

    def call_model(  # noqa: C901, PLR0912, PLR0915
        self,
        role: str,
        prompt: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> CallResultDTO:
        """Chiama i modelli della catena e passa subito al successivo su errore provider."""
        opts = options or CallOptionsDTO()
        messages = [{"role": "user", "content": prompt}]
        if opts.error_feedback:
            msg = f"ERRORE PRECEDENTE:\n{opts.error_feedback}\n\nCorreggi e riprova."
            messages.append({"role": "user", "content": msg})

        models = self._config.get("models", {})
        chain = [model_id for model_id in self.get_chain(role) if model_id in models]
        if not chain:
            chain = [self._primary_model_group(role)]

        provider_errors: list[str] = []
        for model_group in chain:
            try:
                kwargs: dict[str, Any] = {
                    "model": model_group,
                    "messages": messages,
                    "stream": True,
                    "disable_fallbacks": True,
                    "num_retries": 0,
                }
                if opts.temperature_override is not None:
                    kwargs["temperature"] = opts.temperature_override

                deadline = (
                    time.monotonic() + self._max_call_seconds if self._max_call_seconds else None
                )
                chunks: list[Any] = []
                stream = self._router.completion(**kwargs)
                try:
                    for chunk in stream:
                        if deadline is not None and time.monotonic() > deadline:
                            with suppress(Exception):
                                if hasattr(stream, "close"):
                                    stream.close()  # type: ignore[attr-defined]
                            raise Timeout(
                                message=f"Watchdog {self._max_call_seconds:g}s exceeded",
                                model=model_group,
                                llm_provider="watchdog",
                            )
                        chunks.append(chunk)
                finally:
                    with suppress(Exception):
                        if hasattr(stream, "close"):
                            stream.close()  # type: ignore[attr-defined]
                response = stream_chunk_builder(chunks, messages=messages)
                if response is None:
                    msg_err = (
                        "L'output del modello è vuoto. "
                        "Il modello potrebbe aver esaurito i token nel ragionamento CoT. "
                        "Rispondere ESCLUSIVAMENTE con JSON valido."
                    )
                    payload = {"schema": schema.__name__, "raw": ""}
                    raise ModelOutputContractError(msg_err, payload=payload)
                msg = response.choices[0].message
                content = getattr(msg, "content", None) or ""
                cleaned_json = self._extract_json_payload(content)

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
            except _LITELLM_PROVIDER_EXCEPTIONS as e:
                provider_errors.append(f"{model_group}: {e}")
                _log.warning(
                    "Modello '%s' fallito per il ruolo '%s': passo immediatamente al successivo.",
                    model_group,
                    role,
                )

        details = "; ".join(provider_errors)
        raise LLMClientError(f"Catena {role} esaurita: {details}")

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
                loop = get_event_loop()
                if not loop.is_closed() and not loop.is_running():
                    loop.run_until_complete(close_litellm_async_clients())

        with suppress(Exception):
            if isinstance(in_memory_llm_clients_cache, dict):
                in_memory_llm_clients_cache.clear()

    @classmethod
    def _build_model_list(cls, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Costruisce un model group distinto per ogni modello della configurazione.

        Il gateway (`pool`) identifica solo l'endpoint condiviso e non deve diventare
        il gruppo di routing: se più modelli condividono il gateway, un errore su uno
        di essi deve poter passare immediatamente al modello successivo della catena.
        """
        models = config.get("models", {})
        chains = config.get("chains", {})
        ordered_model_ids = list(
            dict.fromkeys(model_id for chain in chains.values() for model_id in chain)
        )
        ordered_model_ids.extend(
            model_id for model_id in models if model_id not in ordered_model_ids
        )
        return [
            {"model_name": model_id, "litellm_params": cls._make_litellm_params(models[model_id])}
            for model_id in ordered_model_ids
            if model_id in models
        ]

    @staticmethod
    def _make_litellm_params(mc: dict[str, Any]) -> dict[str, Any]:
        """Costruisce il dizionario dei parametri litellm_params per una configurazione modello."""
        params: dict[str, Any] = {
            "model": f"{mc['provider']}/{mc['model']}",
            "api_key": mc["api_key"],
            "temperature": mc["temperature"],
            "timeout": mc.get("request_timeout", 120),
        }
        if "max_tokens" in mc:
            params["max_tokens"] = mc["max_tokens"]
        if "base_url" in mc:
            params["api_base"] = mc["base_url"]
        if mc.get("rpm") is not None:
            params["rpm"] = mc["rpm"]
        if mc.get("tpm") is not None:
            params["tpm"] = mc["tpm"]
        return params

    @staticmethod
    def _build_fallbacks(config: dict[str, Any]) -> list[dict[str, list[str]]]:
        """Costruisce fallback immediati tra modelli consecutivi della stessa catena."""
        fallbacks: list[dict[str, list[str]]] = []
        models = config.get("models", {})
        chains = config.get("chains", {})

        seen_chains: set[tuple[str, ...]] = set()
        for model_ids in chains.values():
            chain = list(dict.fromkeys(model_id for model_id in model_ids if model_id in models))
            key = tuple(chain)
            if key in seen_chains or len(chain) <= 1:
                continue
            seen_chains.add(key)
            fallbacks.extend({chain[i]: chain[i + 1 :]} for i in range(len(chain) - 1))
        return fallbacks
