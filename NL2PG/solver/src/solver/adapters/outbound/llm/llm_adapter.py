"""Adattatore outbound per l'invocazione di modelli LLM con failover automatico via LiteLLM Router.

:author: Riccardo Morabito
"""

from logging import CRITICAL as LOG_CRITICAL, getLogger
from sys import modules
from typing import Any, Callable

from httpx import HTTPError
from json import loads as json_loads
from litellm import Router, stream_chunk_builder
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

from solver.domain.exceptions import LLMSolverError
from solver.domain.ports.outbound.llm_port import LLMGeneratorPort

_log = getLogger("solver.adapters.llm")

getLogger("LiteLLM").setLevel(LOG_CRITICAL)
getLogger("LiteLLM Router").setLevel(LOG_CRITICAL)
getLogger("LiteLLM Proxy").setLevel(LOG_CRITICAL)

litellm_mod = modules["litellm"]
litellm_mod.suppress_debug_info = True
litellm_mod.turn_off_message_logging = True
litellm_mod.set_verbose = False
litellm_mod.callbacks = []
litellm_mod.success_callback = []
litellm_mod.failure_callback = []
litellm_mod.input_callback = []
litellm_mod.service_callback = []
litellm_mod.telemetry = False

for _cb_attr in ("_async_success_callback", "_async_failure_callback", "_async_input_callback"):
    if hasattr(litellm_mod, _cb_attr):
        setattr(litellm_mod, _cb_attr, [])

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


class LLMClientAdapter(LLMGeneratorPort):
    """Client per l'invocazione di modelli LLM con failover automatico via LiteLLM Router."""

    @staticmethod
    def _noop_service_hook(*_args: Any, **_kwargs: Any) -> None:
        """Hook no-op per sopprimere i logger interni di LiteLLM."""
        return

    @staticmethod
    def _clean_assistant_message(msg: Any) -> dict[str, Any]:
        """Depura il dizionario del messaggio da proprietà proprietarie incompatibili con le API."""
        raw = msg.model_dump() if hasattr(msg, "model_dump") else dict(msg)
        for bad_key in ("reasoning_content", "thought", "reasoning"):
            raw.pop(bad_key, None)
        return raw

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Inizializza il client configurando il router LiteLLM con i provider e i fallback."""
        self._config = config or {}
        self._chains: dict[str, list[str]] = self._config.get("chains", {})
        self._models: dict[str, dict[str, Any]] = self._config.get("models", {})

        strategy = self._config.get("routing_strategy", "simple-shuffle")
        retry_cfg = self._config.get("retry", {})
        num_retries = retry_cfg.get("num_retries", 2)
        cooldown_time = 0
        allowed_fails = 999999
        self._stream_timeout = retry_cfg.get("stream_timeout", 60)

        self._router = Router(
            model_list=self._build_model_list(self._config),
            fallbacks=self._build_fallbacks(self._config),
            routing_strategy=strategy,
            num_retries=num_retries,
            cooldown_time=cooldown_time,
            allowed_fails=allowed_fails,
            stream_timeout=self._stream_timeout,
            set_verbose=False,
        )

    def call_with_tools(
        self,
        model_role: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], tuple[str, bool]],
        max_iterations: int = 5,
    ) -> tuple[str, list[dict[str, Any]], str]:
        """Esegue il loop agentico di Tool Calling con failover nativo del Router LiteLLM."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        trace: list[dict[str, Any]] = []
        model_identifier = model_role

        for iteration in range(1, max_iterations + 1):
            kwargs = self._make_completion_kwargs(model_role, messages, tools)
            try:
                chunks = list(self._router.completion(**kwargs))
                response = stream_chunk_builder(chunks, messages=messages)
                if not response or not response.choices:
                    continue

                msg = response.choices[0].message
                tool_calls = getattr(msg, "tool_calls", None) or []

                if tool_calls:
                    messages.append(self._clean_assistant_message(msg))
                    self._process_tool_calls(tool_calls, tool_executor, trace, messages, iteration)
                    continue

                content = getattr(msg, "content", "") or ""
                if content.strip():
                    return content, trace, model_identifier

            except _LITELLM_PROVIDER_EXCEPTIONS as e:
                _log.warning("Iterazione %d modello %s: %s", iteration, model_role, e)
                if iteration == max_iterations and not trace:
                    msg_fail = (
                        f"Modello '{model_role}' fallito dopo {max_iterations} tentativi: {e}"
                    )
                    raise LLMSolverError(msg_fail) from e

        final_content = self._request_forced_final_response(model_role, messages)
        return final_content, trace, model_identifier

    def _make_completion_kwargs(
        self, target_model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Costruisce il dizionario di parametri per la chiamata a LiteLLM."""
        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "stream_timeout": self._stream_timeout,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    def _process_tool_calls(
        self,
        tool_calls: list[Any],
        tool_executor: Callable[[str, dict[str, Any]], tuple[str, bool]],
        trace: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        iteration: int,
    ) -> None:
        """Elabora le chiamate agli strumenti richieste dal modello."""
        for tc in tool_calls:
            call_id = getattr(tc, "id", "") or "call_unknown"
            func = getattr(tc, "function", None)
            name = getattr(func, "name", "")
            raw_args = getattr(func, "arguments", "{}")

            args = json_loads(raw_args) if isinstance(raw_args, str) else raw_args
            out_summary, success = tool_executor(name, args)

            trace.append(
                {
                    "tool_name": name,
                    "arguments": args,
                    "output_summary": out_summary,
                    "step": iteration,
                    "success": success,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": out_summary,
                }
            )

    def _request_forced_final_response(
        self, model_role: str, messages: list[dict[str, Any]]
    ) -> str:
        """Forza un turno conclusivo senza strumenti per ottenere il codice finale."""
        messages.append(
            {
                "role": "user",
                "content": (
                    "Hai terminato le verifiche con gli strumenti. Ora fornisci ESCLUSIVAMENTE "
                    "la risposta definitiva con il solo codice finale (SQL o Datalog o DDL), "
                    "senza spiegazioni discorsive, terminando con il punto o punto e virgola."
                ),
            }
        )
        kwargs = self._make_completion_kwargs(model_role, messages, tools=[])
        try:
            chunks = list(self._router.completion(**kwargs))
            resp = stream_chunk_builder(chunks, messages=messages)
            if resp and resp.choices:
                return getattr(resp.choices[0].message, "content", "") or ""
        except _LITELLM_PROVIDER_EXCEPTIONS as e:
            _log.warning("Errore durante la richiesta di risposta finale forzata: %s", e)
        return ""

    @staticmethod
    def _build_model_list(config: dict[str, Any]) -> list[dict[str, Any]]:
        """Costruisce l'elenco dei modelli registrati per il Router LiteLLM."""
        models = config.get("models", {})
        chains = config.get("chains", {})
        model_list: list[dict[str, Any]] = []
        registered: set[tuple[str, str]] = set()

        for model_id, model_cfg in models.items():
            if (model_id, model_id) not in registered:
                params = LLMClientAdapter._make_params(model_cfg)
                model_list.append({"model_name": model_id, "litellm_params": params})
                registered.add((model_id, model_id))

        for role, mid_list in chains.items():
            if not mid_list:
                continue
            first_mid = mid_list[0]
            if first_mid in models and (role, first_mid) not in registered:
                params = LLMClientAdapter._make_params(models[first_mid])
                model_list.append({"model_name": role, "litellm_params": params})
                registered.add((role, first_mid))

        return model_list

    @staticmethod
    def _make_params(model_cfg: dict[str, Any]) -> dict[str, Any]:
        """Costruisce i parametri litellm per una configurazione."""
        provider = model_cfg.get("provider", "openai")
        raw_model = model_cfg.get("model", "")
        model_name = f"{provider}/{raw_model}"
        params: dict[str, Any] = {
            "model": model_name,
            "api_key": model_cfg.get("api_key", "dummy-key"),
            "temperature": model_cfg.get("temperature", 0.0),
            "timeout": model_cfg.get("request_timeout", 60),
        }
        if "base_url" in model_cfg:
            params["api_base"] = model_cfg["base_url"]
        return params

    @staticmethod
    def _build_fallbacks(config: dict[str, Any]) -> list[dict[str, list[str]]]:
        """Costruisce le definizioni di fallback per le catene configurate."""
        chains = config.get("chains", {})
        fallbacks: list[dict[str, list[str]]] = []
        for role, mid_list in chains.items():
            if len(mid_list) > 1:
                fallbacks.append({role: mid_list[1:]})
                for idx, mid in enumerate(mid_list):
                    if idx < len(mid_list) - 1:
                        fallbacks.append({mid: mid_list[idx + 1 :]})
        return fallbacks
