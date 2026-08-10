"""Adattatore outbound per la configurazione del logging centralizzato.

:author: Riccardo Morabito
"""

from datetime import datetime, timezone
from logging import WARNING, NullHandler, getLogger
from logging.config import dictConfig
from os import getpid
from pathlib import Path

from litellm import verbose_logger
from orjson import loads as orjson_loads

from bench.domain.exceptions import LoggingConfigError, SymlinkError
from bench.domain.ports.outbound.logger_port import LoggerPort


class LoggingAdapter(LoggerPort):
    """Adattatore concreto per la configurazione del logging del benchmark."""

    def __init__(self, level: str = "DEBUG", run_id: str = ""):
        """Inizializza la configurazione con livello e identificativo run_id."""
        self._level = level
        self._run_id = run_id
        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
        self._config_dir = base_dir / "config"
        self._log_dir = base_dir / "logs"

    def get_config_dir(self) -> Path:
        """Restituisce la directory contenente i file di configurazione."""
        return self._config_dir

    def get_log_dir(self) -> Path:
        """Restituisce la directory dei file di log."""
        return self._log_dir

    def configure(self) -> None:
        """Applica la configurazione del logging dal file JSON ed integra le dipendenze esterne."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._new_log_path()
        self._ensure_latest_symlink(log_path)

        cfg_path = self._config_dir / "logging.json"
        if not cfg_path.exists():
            raise LoggingConfigError(
                f"File di configurazione del logging assente: {cfg_path}. "
                "Assicurarsi che sia presente."
            )
        cfg = orjson_loads(cfg_path.read_bytes())

        cfg["handlers"]["file"]["filename"] = str(log_path)
        cfg["handlers"]["file"]["level"] = self._level
        dictConfig(cfg)
        self._configure_dependency_loggers()

    def _configure_dependency_loggers(self) -> None:
        """Integrazione e instradamento dei logger delle dipendenze nel file di log unico."""
        verbose_logger.handlers.clear()
        verbose_logger.addHandler(NullHandler())
        verbose_logger.propagate = True

        for pkg in ("httpcore", "asyncio", "urllib3", "filelock"):
            getLogger(pkg).setLevel(WARNING)

        for pkg in (
            "LiteLLM",
            "litellm",
            "LiteLLM Router",
            "LiteLLM Proxy",
            "httpx",
            "openai",
            "openai._base_client",
            "langchain",
            "langgraph",
            "sqlalchemy",
            "psycopg",
        ):
            logger_obj = getLogger(pkg)
            logger_obj.handlers.clear()
            logger_obj.addHandler(NullHandler())
            logger_obj.propagate = True

    def _new_log_path(self) -> Path:
        """Genera il percorso del file di log contenente timestamp, run_id e PID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pid = getpid()
        prefix = (
            f"bench_{timestamp}_{self._run_id}_{pid}"
            if self._run_id
            else f"bench_{timestamp}_{pid}"
        )
        return self._log_dir / f"{prefix}.log"

    def _ensure_latest_symlink(self, log_path: Path) -> None:
        """Mantiene il symlink bench.log aggiornato all'ultimo file di log."""
        latest = self._log_dir / "bench.log"
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            latest.symlink_to(log_path.name)
        except OSError as e:
            raise SymlinkError(str(latest), payload=str(log_path)) from e
