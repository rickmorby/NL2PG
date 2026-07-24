"""Modulo per la configurazione centralizzata del logging del benchmark.

:author: Riccardo Morabito
"""

from json import load
from logging import WARNING, getLogger
from logging.config import dictConfig
from pathlib import Path
from datetime import datetime, timezone
from os import getpid
from bench.exception import LoggingConfigError, SymlinkError


class LoggingConfig:
    """Configurazione del logging del benchmark."""

    def __init__(self, level: str = "DEBUG", run_id: str = ""):
        """Inizializza la configurazione con livello e run_id."""
        self._level = level
        self._run_id = run_id
        self._config_dir = Path(__file__).resolve().parent.parent.parent.parent / "config"
        self._log_dir = Path(__file__).resolve().parent.parent.parent.parent / "logs"

    def get_config_dir(self) -> Path:
        """Restituisce la directory di configurazione."""
        return self._config_dir

    def get_log_dir(self) -> Path:
        """Restituisce la directory dei log."""
        return self._log_dir

    def configure(self) -> None:
        """Applica la configurazione del logging."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._new_log_path()
        self._ensure_latest_symlink(log_path)

        cfg_path = self._config_dir / "logging.json"
        if not cfg_path.exists():
            raise LoggingConfigError(
                f"File di configurazione del logging assente: {cfg_path}. "
                "Assicurarsi che sia presente."
            )
        with open(cfg_path, encoding="utf-8") as f:
            cfg = load(f)

        cfg["handlers"]["file"]["filename"] = str(log_path)
        cfg["handlers"]["file"]["level"] = self._level
        dictConfig(cfg)
        self._quiet_network_loggers()

    def _quiet_network_loggers(self) -> None:
        """Silenzia i logger delle librerie di rete a WARNING."""
        for pkg in (
            "httpx", "httpcore", "openai", "openai._base_client",
            "langchain", "langgraph",
        ):
            getLogger(pkg).setLevel(WARNING)

    def _new_log_path(self) -> Path:
        """Genera il path del file di log con timestamp, run_id e PID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pid = getpid()
        prefix = (
            f"bench_{timestamp}_{self._run_id}_{pid}"
            if self._run_id
            else f"bench_{timestamp}_{pid}"
        )
        return self._log_dir / f"{prefix}.log"

    def _ensure_latest_symlink(self, log_path: Path) -> None:
        """Mantiene un symlink bench.log che punta all'ultimo file di log."""
        latest = self._log_dir / "bench.log"
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            latest.symlink_to(log_path.name)
        except OSError as e:
            raise SymlinkError(str(latest), payload=str(log_path)) from e
