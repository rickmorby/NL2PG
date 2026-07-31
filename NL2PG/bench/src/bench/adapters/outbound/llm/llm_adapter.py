"""Adattatore outbound per l'invocazione di modelli LLM con failover automatico via liteLLM Router.

:author: Riccardo Morabito
"""

from json import loads as json_loads
from re import (
    DOTALL as re_DOTALL,
    IGNORECASE as re_IGNORECASE,
    search as re_search,
    sub as re_sub,
)
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
                params = {
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

                entry = {
                    "model_name": role,
                    "litellm_params": params,
                }
                model_list.append(entry)

        return model_list


def _extract_json_payload(text: str) -> str:
    """Estrae l'oggetto o array JSON finale da un testo LLM scartando CoT e tag di ragionamento."""
    if not text:
        return ""

    raw = text.strip()

    try:
        json_loads(raw)
        return raw
    except Exception:
        pass

    tags = "think|thinking|thought|reasoning|reflection|rationale|chain_of_thought"

    cleaned = re_sub(
        r"<(" + tags + r")\b[^>]*>.*?</\1>",
        "",
        raw,
        flags=re_DOTALL | re_IGNORECASE,
    )
    cleaned = re_sub(
        r"\[(" + tags + r")\].*?\[/\1\]",
        "",
        cleaned,
        flags=re_DOTALL | re_IGNORECASE,
    )

    cleaned = re_sub(r"<(" + tags + r")\b[^>]*>", "", cleaned, flags=re_IGNORECASE)
    cleaned = re_sub(r"\[(" + tags + r")\]", "", cleaned, flags=re_IGNORECASE)
    cleaned = cleaned.strip()

    if "```" in cleaned:
        m = re_search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re_DOTALL | re_IGNORECASE)
        if m:
            cleaned = m.group(1).strip()
        else:
            cleaned = re_sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re_sub(r"\n?```$", "", cleaned).strip()

    extracted = _find_balanced_json(cleaned)
    if extracted:
        return extracted

    return cleaned


def _find_balanced_json(candidate: str) -> str | None:
    """Individua il confine esatto del JSON bilanciando parentesi graffe/quadre e stringhe."""
    start_indices = [i for i, ch in enumerate(candidate) if ch in ("{", "[")]
    valid_matches: list[str] = []
    for start in start_indices:
        stack: list[str] = []
        in_string = False
        escape = False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch in ("{", "["):
                    stack.append(ch)
                elif ch in ("}", "]"):
                    if not stack:
                        break
                    opening = stack.pop()
                    if (opening == "{" and ch != "}") or (opening == "[" and ch != "]"):
                        break
                    if not stack:
                        substr = candidate[start : i + 1]
                        try:
                            json_loads(substr)
                            valid_matches.append(substr)
                        except Exception:
                            pass
    return valid_matches[-1] if valid_matches else None


