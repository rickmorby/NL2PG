"""Adapter per caricamento configurazione da filesystem.

:author: Riccardo Morabito
"""

from hashlib import sha256
from json import dumps, loads
from pathlib import Path
from tomllib import load as toml_load

from bench.domain.exceptions import (
    ConfigurationMissingFieldError,
    ProviderConfigError,
    handle_exception,
)
from bench.domain.models.category import CategoryDTO
from bench.domain.ports.outbound.config_port import ConfigPort


class ConfigAdapter(ConfigPort):
    """Carica providers, bench, categorie e DSN da file JSON/TOML."""

    def __init__(self, config_dir: Path) -> None:
        """Salva il percorso della directory di configurazione."""
        self._dir = config_dir

    def load_providers(self) -> dict:
        """Restituisce il contenuto di providers.json come dict."""
        path = self._dir / "providers.json"
        if not path.exists():
            msg = (
                f"File di configurazione providers.json non trovato in '{self._dir}'. "
                "Il file andrebbe configurato per il corretto funzionamento dei provider LLM."
            )
            exc = ProviderConfigError(msg, payload={"path": str(path)})
            handle_exception(exc)
            return {}
        return loads(path.read_text(encoding="utf-8"))

    def load_bench(self) -> dict:
        """Restituisce il contenuto di bench.toml come dict, o dict vuoto se assente."""
        path = self._dir / "bench.toml"
        if not path.exists():
            msg = (
                f"File di configurazione bench.toml non trovato in '{self._dir}'. "
                "Il file andrebbe configurato per definire i parametri del benchmark."
            )
            payload = {"path": str(path), "file": "bench.toml"}
            exc = ConfigurationMissingFieldError(msg, payload=payload)
            handle_exception(exc)
            return {}
        with open(path, "rb") as f:
            return toml_load(f)

    def load_categories(self) -> dict[str, CategoryDTO]:
        """Restituisce un dict {id: CategoryDTO} dal file categories.json."""
        path = self._dir / "categories.json"
        if not path.exists():
            msg = (
                f"File di configurazione categories.json non trovato in '{self._dir}'. "
                "Il file andrebbe configurato per caricare le categorie del benchmark."
            )
            payload = {"path": str(path), "file": "categories.json"}
            exc = ConfigurationMissingFieldError(msg, payload=payload)
            handle_exception(exc)
            return {}
        data = loads(path.read_text(encoding="utf-8"))
        return {c["id"]: CategoryDTO(**c) for c in data["categories"]}

    def dsn(self, key: str) -> str:
        """Restituisce il DSN da bench.toml o solleva un'eccezione di configurazione con fallback.

        :param key: Chiave del DSN richiesta ('db_dsn', 'sandbox_dsn' o 'meta_dsn').
        :return: Stringa di connessione DSN PostgreSQL.
        """
        default_map = {
            "db_dsn": "postgresql://bench:bench@127.0.0.1:5432/bench_sandbox",
            "sandbox_dsn": "postgresql://bench:bench@127.0.0.1:5432/bench_sandbox",
            "meta_dsn": "postgresql://bench:bench@127.0.0.1:5432/bench_meta",
        }

        bench = self.load_bench()
        run_cfg = bench.get("run", {})
        toml_val = run_cfg.get(key)
        if not toml_val and key in ("db_dsn", "sandbox_dsn"):
            toml_val = run_cfg.get("db_dsn") or run_cfg.get("sandbox_dsn")

        if toml_val:
            return toml_val

        default_val = default_map.get(key, "")
        msg = (
            f"Il campo '{key}' non è stato trovato nel file bench.toml sotto [run]. "
            f"Viene utilizzato il valore di fallback '{default_val}'."
        )
        exc = ConfigurationMissingFieldError(
            msg,
            payload={"key": key, "default": default_val, "file": "bench.toml"},
        )
        handle_exception(exc)
        return default_val

    def config_hash(self, cfg: dict) -> str:
        """Calcola l'hash SHA256 di un dict di configurazione."""
        payload = dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
        return sha256(payload.encode("utf-8")).hexdigest()[:16]
