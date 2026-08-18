"""Modulo base astratto per tutti gli agent della pipeline di generazione.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any

from orjson import dumps as orjson_dumps
from psycopg.errors import Error as PgError
from pydantic import BaseModel, ValidationError
from sqlglot.errors import ParseError

from bench.domain.exceptions import BenchException, LLMClientError, ModelOutputContractError
from bench.domain.models.llm import CallOptionsDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.example_port import ExamplePort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort

_log = getLogger("bench.application.agents")


class AbstractAgent(ABC):
    """Base astratta per agent che generano componenti del task via LLM con retry loop."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        examples: ExamplePort | None = None,
    ) -> None:
        """Inietta le porte outbound per LLM, prompt, configurazione ed esempi."""
        self._llm = llm
        self._prompts = prompts
        self._config = config
        self._examples = examples

    @abstractmethod
    def prompt_name(self) -> str:
        """Restituisce il nome del template prompt (senza .txt)."""

    @abstractmethod
    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs da passare al template prompt."""

    @abstractmethod
    def output_schema(self) -> type[BaseModel]:
        """Restituisce la classe Pydantic per lo structured output dell'LLM."""

    def validate(self, _output: Any, _state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Override per validazione extra; restituisce (ok, errore, aggiornamenti_extra)."""
        return True, "", {}

    @abstractmethod
    def build_updates(self, output: Any, state: TaskStateDTO) -> dict:
        """Mappa l'output LLM nei campi dello stato da aggiornare."""

    def run(self, state: TaskStateDTO, chain_role: str = "default") -> dict:
        """Esegue prompt->LLM->validazione con retry loop; restituisce aggiornamenti stato."""
        err = ""
        last_model = ""
        name = self.prompt_name()
        max_attempts = self._max_retries(state)

        for i in range(1, max_attempts + 1):
            prompt = self._prompts.load(name, **self.build_kwargs(state))
            opts = CallOptionsDTO(error_feedback=err if err else None)
            try:
                result = self._llm.call_model(chain_role, prompt, self.output_schema(), opts)
                last_model = result.model_used
                output = result.output
                ok, val_err, extra = self.validate(output, state)
                if ok:
                    updates = self.build_updates(output, state)
                    updates.update(extra)
                    updates["last_model"] = result.model_used
                    updates["last_error"] = ""
                    return updates
                err = f"Violazione vincoli contratto '{name}': {val_err}"
                _log.info(
                    "Nodo '%s' (tentativo %d/%d) fallito: %s",
                    name,
                    i,
                    max_attempts,
                    val_err,
                )
            except (ModelOutputContractError, ValidationError) as e:
                err = f"Errore contratto output '{name}': {e}"
                _log.info(
                    "Nodo '%s' (tentativo %d/%d) errore contratto: %s",
                    name,
                    i,
                    max_attempts,
                    e,
                )
            except LLMClientError as e:
                err = f"Errore infrastruttura LLM per nodo '{name}': {e}"
                _log.warning("Nodo '%s' interrotto per errore client LLM: %s", name, e)
                break
            except (
                BenchException,
                PgError,
                ParseError,
                ValueError,
                TypeError,
                KeyError,
            ) as e:
                err = f"Errore invocazione agente '{name}': {e}"
                _log.info(
                    "Nodo '%s' (tentativo %d/%d) eccezione: %s",
                    name,
                    i,
                    max_attempts,
                    e,
                )

        _log.warning("Nodo '%s' esaurito dopo %d tentativi. Task scartato.", name, max_attempts)
        return {"verdict": "scrapped", "last_error": err, "last_model": last_model}

    def _few_shot(self, state: TaskStateDTO) -> str:
        """Restituisce gli esempi few-shot del ruolo dell'agente, o stringa vuota se assenti.

        Unico punto di accesso agli esempi: il ruolo deriva da ``prompt_name()``
        e la resa (JSON + separatore) è centralizzata qui, non negli agenti.
        """
        if self._examples is None:
            return ""
        examples = self._examples.load(state.category, self.prompt_name())
        return "\n---\n".join(orjson_dumps(e).decode() for e in examples)

    def _max_retries(self, _state: TaskStateDTO) -> int:
        """Restituisce il numero massimo di tentativi configurato."""
        return self._config.retry_max_per_node()
