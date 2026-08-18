"""Modulo per la gestione globale delle eccezioni del benchmark basato su singledispatch.

:author: Riccardo Morabito
"""

from functools import singledispatch
from logging import getLogger
from sys import exit as sys_exit, modules
from rich.console import Console

from bench.domain.exceptions.clients_exc import (
    DatabaseClientError,
    LLMClientError,
    ModelOutputContractError,
    ProviderConfigError,
    SpecDuplicatedError,
)
from bench.domain.exceptions.config_exc import ConfigurationMissingFieldError
from bench.domain.exceptions.domain_exc import DomainValidationError
from bench.domain.exceptions.logging_exc import LoggingConfigError, SymlinkError

_log = getLogger("bench.domain.exceptions")
_console = Console(stderr=True)


@singledispatch
def handle_exception(exc: BaseException) -> None:
    """Handler predefinito per eccezioni generiche non gestite specificamente."""
    _log.critical("%s: %s", type(exc).__name__, exc)
    _console.print(f"[bold red][ERROR][/bold red] {type(exc).__name__}: {exc}")
    sys_exit(1)


@handle_exception.register(SymlinkError)
def _handle_symlink_error(exc: SymlinkError) -> None:
    """Handler per SymlinkError: i log sono registrati sul file dedicato."""
    log_path = getattr(exc, "payload", None) or "file dedicato"
    _log.warning("Symlink bench.log non creato. I log sono comunque registrati su: %s", log_path)


@handle_exception.register(DomainValidationError)
def _handle_domain_validation_error(exc: DomainValidationError) -> None:
    """Handler per violazioni delle regole d'invariante di dominio."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(ConfigurationMissingFieldError)
def _handle_config_missing_field_error(exc: ConfigurationMissingFieldError) -> None:
    """Handler per campi o file di configurazione mancanti con valore di fallback."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(ModelOutputContractError)
def _handle_model_output_contract_error(exc: ModelOutputContractError) -> None:
    """Handler per errori di contratto o validazione dell'output generato dall'LLM."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(SpecDuplicatedError)
def _handle_spec_duplicated_error(exc: SpecDuplicatedError) -> None:
    """Handler per tentativi di generazione di specifica duplicata."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(ProviderConfigError)
def _handle_provider_config_error(exc: ProviderConfigError) -> None:
    """Handler per ProviderConfigError."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(LoggingConfigError)
def _handle_logging_config_error(exc: LoggingConfigError) -> None:
    """Handler per LoggingConfigError."""
    _log.warning("%s", exc.message)
    _console.print(f"[bold yellow][WARNING][/bold yellow] {exc.message}")


@handle_exception.register(DatabaseClientError)
def _handle_database_client_error(exc: DatabaseClientError) -> None:
    """Handler per errori di connessione o esecuzione verso PostgreSQL."""
    _log.error("Errore infrastruttura database PostgreSQL: %s", exc.message)
    _console.print(f"[bold red][DATABASE ERROR][/bold red] {exc.message}")


@handle_exception.register(LLMClientError)
def _handle_llm_client_error(exc: LLMClientError) -> None:
    """Handler per errori irrevocabili di invocazione verso i provider LLM."""
    _log.error("Errore client LLM / Provider: %s", exc.message)
    _console.print(f"[bold red][LLM ERROR][/bold red] {exc.message}")


def _global_excepthook(
    _exc_type: type[BaseException],
    exc_value: BaseException,
    _exc_tb: object,
) -> None:
    """Hook globale assegnato a sys.excepthook che delega il dispatch a handle_exception."""
    handle_exception(exc_value)


def install_global_handler() -> None:
    """Installa l'handler globale su sys.excepthook."""
    modules["sys"].excepthook = _global_excepthook
