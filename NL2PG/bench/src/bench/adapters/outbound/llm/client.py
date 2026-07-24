"""Adattatore outbound per generazione ed orchestrazione LLM tramite LangChain.

:author: Riccardo Morabito
"""

from logging import getLogger
from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from pydantic import BaseModel
from bench.domain.exceptions import LLMClientError
from bench.domain.models.llm import CallOptionsDTO, CallResultDTO
from bench.domain.ports.outbound.llm import LLMGeneratorPort

_log = getLogger("bench.adapters.llm")


class LLMClientAdapter(LLMGeneratorPort):
    """Adattatore per l'istanziazione e l'orchestrazione nativa delle catene LLM con LangChain."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Inizializza l'adattatore memorizzando il dizionario di configurazione."""
        self._config = config or {}

    def get_config(self) -> dict[str, Any]:
        """Restituisce il dizionario di configurazione dell'adattatore."""
        return self._config

    def get_chain(self, role: str) -> list[str]:
        """Restituisce la catena di modelli configurata per un dato ruolo."""
        chains = self._config.get("chains", {})
        return list(chains.get(role, []))

    def create_model_runnable(
        self,
        model_id: str,
        schema: type[BaseModel] | type,
        temperature_override: float | None = None,
        attempts: int = 3,
    ) -> Runnable:
        """Crea un Runnable per un modello usando init_chat_model e retry nativo."""
        models_cfg = self._config.get("models", {})
        m = models_cfg.get(model_id)
        if not m:
            raise LLMClientError(f"Configurazione assente per il modello {model_id!r}.")

        m_kwargs = dict(m)
        provider = m_kwargs.pop("provider", "openai")
        model_name = m_kwargs.pop("model", model_id)
        so_method = m_kwargs.pop("structured_output_method", None)

        if temperature_override is not None:
            m_kwargs["temperature"] = temperature_override

        chat_model = init_chat_model(model_name, model_provider=provider, **m_kwargs)

        structured_runnable = (
            chat_model.with_structured_output(schema, method=so_method)
            if so_method
            else chat_model.with_structured_output(schema)
        )

        return structured_runnable.with_retry(
            stop_after_attempt=attempts,
            wait_exponential_jitter=True,
        )

    def build_chain_runnable(
        self,
        role: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> Runnable:
        """Costruisce una catena Runnable con retry e fallbacks nativi tra modelli."""
        opts = options or CallOptionsDTO()
        model_ids = self.get_chain(role)
        if not model_ids:
            raise LLMClientError(f"Nessuna catena di modelli configurata per il ruolo {role!r}.")

        force_model = opts.get_force_model()
        if force_model:
            if force_model not in model_ids:
                msg = f"Modello forzato {force_model!r} non in catena ruolo {role!r}."
                raise LLMClientError(msg)
            model_ids = model_ids[model_ids.index(force_model) :]

        retry_cfg = self._config.get("retry", {})
        attempts = retry_cfg.get("per_model_attempts", 3)

        runnables: list[Runnable] = []
        for model_id in model_ids:
            runnable = self.create_model_runnable(
                model_id=model_id,
                schema=schema,
                temperature_override=opts.get_temperature_override(),
                attempts=attempts,
            )
            runnables.append(runnable)

        primary_runnable = runnables[0]
        if len(runnables) > 1:
            return primary_runnable.with_fallbacks(runnables[1:])
        return primary_runnable

    def call_model(
        self,
        role: str,
        prompt: str,
        schema: type[BaseModel] | type,
        options: CallOptionsDTO | None = None,
    ) -> CallResultDTO:
        """Invoca la catena Runnable e restituisce il risultato in CallResultDTO."""
        opts = options or CallOptionsDTO()
        runnable_chain = self.build_chain_runnable(role, schema, opts)

        full_prompt = prompt
        feedback = opts.get_error_feedback()
        if feedback:
            full_prompt = f"{prompt}\n\nERRORE PRECEDENTE:\n{feedback}\n\nCorreggi e riprova."

        try:
            output = runnable_chain.invoke(full_prompt)
            model_used = opts.get_force_model() or self.get_chain(role)[0]
            return CallResultDTO(
                output=output,
                model_used=model_used,
            )
        except Exception as e:
            _log.error("Errore durante l'esecuzione della catena per %s: %s", role, e)
            raise LLMClientError(f"Esecuzione catena fallita per {role!r}: {e}") from e
