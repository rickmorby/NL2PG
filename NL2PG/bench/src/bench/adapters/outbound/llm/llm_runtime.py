"""Configurazione globale del runtime LiteLLM ed eccezioni provider.

Silenzia il logging interno di LiteLLM, disattiva telemetria e callback e
aggrega la tupla delle eccezioni trattabili come fallimenti di provider.

:author: Riccardo Morabito
"""

from logging import CRITICAL as LOG_CRITICAL, getLogger
from warnings import filterwarnings

from httpx import HTTPError
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
from sys import modules

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


def configure_litellm_runtime() -> None:
    """Applica una sola volta le impostazioni globali silenziose di LiteLLM."""
    getLogger("LiteLLM").setLevel(LOG_CRITICAL)
    getLogger("LiteLLM Router").setLevel(LOG_CRITICAL)
    getLogger("LiteLLM Proxy").setLevel(LOG_CRITICAL)

    mod = modules["litellm"]
    mod.suppress_debug_info = True
    mod.turn_off_message_logging = True
    mod.set_verbose = False
    mod.callbacks = []
    mod.success_callback = []
    mod.failure_callback = []
    mod.input_callback = []
    mod.service_callback = []
    mod.telemetry = False
    mod.cache = None
    filterwarnings("ignore", message=r".*DualCache\.async_batch_get_cache.*")
    for attr in ("_async_success_callback", "_async_failure_callback", "_async_input_callback"):
        if hasattr(mod, attr):
            setattr(mod, attr, [])
