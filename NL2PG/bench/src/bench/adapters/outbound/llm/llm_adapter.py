"""Adattatore outbound per l'invocazione di modelli LLM con failover via Router.

``call_model`` orchestra la catena dei modelli del ruolo: streaming con
watchdog wall-clock, passaggio immediato al modello successivo su errore
provider e validazione contrattuale dell'output JSON rispetto allo schema.

:author: Riccardo Morabito
"""

from asyncio import get_event_loop
from contextlib import suppress
from logging import getLogger
from time import monotonic
from typing import Any

from json_repair import repair_json
from litellm import (
    close_litellm_async_clients,
    in_memory_llm_clients_cache,
    stream_chunk_builder,
)
from litellm.exceptions import Timeout
from pydantic import BaseModel, ValidationError

from bench.adapters.outbound.llm.llm_health_checker_adapter import LLMHealthCheckerAdapter
from bench.adapters.outbound.llm.llm_router_factory import (
    build_router,
    primary_model_group,
    resolve_chain,
)
from bench.adapters.outbound.llm.llm_runtime import (
    _LITELLM_PROVIDER_EXCEPTIONS,
    configure_litellm_runtime,
)
from bench.domain.exceptions import LLMClientError, ModelOutputContractError
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO, SystemHealthReportDTO
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort

_log = getLogger("bench.adapters.llm")
configure_litellm_runtime()


class LLMClientAdapter(LLMGeneratorPort):
    """Adattatore per l'invocazione di modelli LLM con failover automatico."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        health_checker: LLMHealthCheckerAdapter | None = None,
    ):
        """Inizializza router e watchdog dalla configurazione dei provider."""
        self._config = config or {}
        self._health_checker = health_checker or LLMHealthCheckerAdapter(self._config)
        retry_cfg = self._config.get("retry", {})
        self._stream_timeout = retry_cfg.get("stream_timeout", 60)
        self._max_call_seconds = float(retry_cfg.get("max_call_seconds", 240))
        self._router = build_router(self._config, self._stream_timeout)

    def get_chain(self, role: str) -> list[str]:
        """Restituisce i model_id abilitati per un ruolo (i disabilitati sono filtrati)."""
        chains = self._config.get("chains", {})
        models = self._config.get("models", {})
        return [
            model_id
            for model_id in chains.get(role, [])
            if models.get(model_id, {}).get("enabled", True)
        ]

    def check_all_providers(self, check_models: bool = True) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello dei provider e dei modelli fisici univoci."""
        return self._health_checker.check_all_providers(check_models=check_models)

    def call_model(
        self,
        role: str,
        prompt: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> CallResultDTO:
        """Chiude la catena del ruolo: al primo errore provider passa al modello successivo."""
        opts = options or CallOptionsDTO()
        messages = self._prepare_messages(prompt, opts)
        models = self._config.get("models", {})
        chain = [m for m in resolve_chain(self._config, role) if m in models]
        if not chain:
            chain = [primary_model_group(self._config, role)]

        provider_errors: list[str] = []
        for model_group in chain:
            try:
                response = self._complete_with_watchdog(
                    model_group, messages, opts.temperature_override
                )
                output = self._validate_output(response, schema)
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
        raise LLMClientError(f"Catena {role} esaurita: {'; '.join(provider_errors)}")

    @staticmethod
    def _prepare_messages(prompt: str, opts: CallOptionsDTO) -> list[dict[str, str]]:
        """Costruisce i messaggi utente, includendo l'eventuale feedback d'errore."""
        messages = [{"role": "user", "content": prompt}]
        if opts.error_feedback:
            feedback = f"ERRORE PRECEDENTE:\n{opts.error_feedback}\n\nCorreggi e riprova."
            messages.append({"role": "user", "content": feedback})
        return messages

    def _complete_with_watchdog(
        self, model_group: str, messages: list[dict[str, str]], temperature: float | None
    ) -> Any:
        """Esegue lo stream del modello applicando il watchdog wall-clock.

        Al superamento della deadline chiude lo stream e solleva ``Timeout``
        cosi' da trattare il modello muto come un qualunque errore provider.
        """
        kwargs: dict[str, Any] = {
            "model": model_group,
            "messages": messages,
            "stream": True,
            "disable_fallbacks": True,
            "num_retries": 0,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        deadline = monotonic() + self._max_call_seconds if self._max_call_seconds else None
        chunks: list[Any] = []
        stream = self._router.completion(**kwargs)
        try:
            for chunk in stream:
                if deadline is not None and monotonic() > deadline:
                    with suppress(Exception):
                        if hasattr(stream, "close"):
                            stream.close()
                    raise Timeout(
                        message=f"Watchdog {self._max_call_seconds:g}s exceeded",
                        model=model_group,
                        llm_provider="watchdog",
                    )
                chunks.append(chunk)
        finally:
            with suppress(Exception):
                if hasattr(stream, "close"):
                    stream.close()

        response = stream_chunk_builder(chunks, messages=messages)
        if response is None:
            raise ValueError("Output del modello vuoto (CoT esaurito?): fallback al successivo.")
        return response

    def _validate_output(self, response: Any, schema: type[BaseModel] | type) -> BaseModel:
        """Estrae e valida il JSON dall'output del modello secondo lo schema atteso."""
        content = getattr(response.choices[0].message, "content", None) or ""
        cleaned_json = repair_json(content.strip(), ensure_ascii=False) if content else ""
        if not cleaned_json:
            msg = f"Output di '{response.model}' vuoto: fallback al successivo."
            raise ValueError(msg)
        try:
            return schema.model_validate_json(cleaned_json)
        except ValidationError as ve:
            msg_err = (
                f"L'output del modello '{response.model}' non rispetta lo schema "
                f"'{schema.__name__}': {ve}. Rispondere ESCLUSIVAMENTE con JSON valido."
            )
            payload = {"schema": schema.__name__, "raw": cleaned_json}
            raise ModelOutputContractError(msg_err, payload=payload) from ve

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
