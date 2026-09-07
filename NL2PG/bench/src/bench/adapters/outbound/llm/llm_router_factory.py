"""Factory del Router LiteLLM a partire dalla configurazione provider.

Traduce la sezione ``models``/``chains``/``retry`` della configurazione nei
parametri del router: un model group per modello fisico, fallback immediati
tra modelli consecutivi di catena e policy di retry/cooldown.

:author: Riccardo Morabito
"""

from typing import Any

from litellm import Router


def enabled_models(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Restituisce i modelli abilitati della configurazione."""
    return {
        model_id: mc for model_id, mc in config.get("models", {}).items() if mc.get("enabled", True)
    }


def resolve_chain(config: dict[str, Any], role: str) -> list[str]:
    """Risolve la catena dei model_id abilitati per un ruolo."""
    chains = config.get("chains", {})
    return [model_id for model_id in chains.get(role, []) if model_id in enabled_models(config)]


def primary_model_group(config: dict[str, Any], role: str) -> str:
    """Risolve il ruolo nel model group del primo modello abilitato della catena."""
    for model_id in resolve_chain(config, role):
        return model_id
    return role


def build_model_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Costruisce un model group distinto per ogni modello abilitato.

    Il gateway (``pool``) identifica solo l'endpoint condiviso e non deve
    diventare gruppo di routing: modelli diversi sullo stesso gateway devono
    potersi fallbackare indipendentemente.
    """
    models = enabled_models(config)
    ordered = list(
        dict.fromkeys(
            model_id
            for chain in config.get("chains", {}).values()
            for model_id in chain
            if model_id in models
        )
    )
    ordered.extend(model_id for model_id in models if model_id not in ordered)
    return [
        {"model_name": model_id, "litellm_params": make_litellm_params(models[model_id])}
        for model_id in ordered
    ]


def make_litellm_params(mc: dict[str, Any]) -> dict[str, Any]:
    """Costruisce i ``litellm_params`` per una singola configurazione modello."""
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


def build_fallbacks(config: dict[str, Any]) -> list[dict[str, list[str]]]:
    """Costruisce i fallback immediati tra modelli consecutivi di ogni catena univoca."""
    fallbacks: list[dict[str, list[str]]] = []
    models = enabled_models(config)
    seen_chains: set[tuple[str, ...]] = set()
    for model_ids in config.get("chains", {}).values():
        chain = list(dict.fromkeys(m for m in model_ids if m in models))
        key = tuple(chain)
        if key in seen_chains or len(chain) <= 1:
            continue
        seen_chains.add(key)
        fallbacks.extend({chain[i]: chain[i + 1 :]} for i in range(len(chain) - 1))
    return fallbacks


def build_router(config: dict[str, Any], stream_timeout: int) -> Router:
    """Istanzia il Router LiteLLM con le policy derivate dalla configurazione."""
    retry_cfg = config.get("retry", {})
    max_fallbacks = max((len(chain) for chain in config.get("chains", {}).values()), default=1) - 1
    return Router(
        model_list=build_model_list(config),
        fallbacks=build_fallbacks(config),
        max_fallbacks=max_fallbacks,
        routing_strategy=config.get("routing_strategy", "simple-shuffle"),
        num_retries=retry_cfg.get("num_retries", 0),
        cooldown_time=retry_cfg.get("cooldown_time_seconds", 0),
        allowed_fails=retry_cfg.get("allowed_fails", 999999),
        optional_pre_call_checks=config.get(
            "optional_pre_call_checks", ["enforce_model_rate_limits"]
        ),
        stream_timeout=stream_timeout,
        set_verbose=False,
        cache_responses=False,
    )
