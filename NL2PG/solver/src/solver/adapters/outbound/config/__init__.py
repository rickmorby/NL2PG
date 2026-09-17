"""Adapter per caricamento configurazione da filesystem per il solver.

:author: Riccardo Morabito
"""

from pathlib import Path
from tomllib import loads as toml_loads
from typing import Any, ClassVar

from orjson import loads as orjson_loads

from solver.domain.exceptions import SolverConfigurationError
from solver.domain.ports.outbound.config_port import ConfigPort


class ConfigAdapter(ConfigPort):
    """Carica providers.json e solver.toml da file."""

    _DEFAULTS: ClassVar[dict[str, dict[str, object]]] = {
        "solver": {
            "max_tool_iterations": 5,
            "max_retries": 3,
            "temperature": 0.2,
            "runs": 1,
        },
        "retry": {
            "num_retries": 0,
            "cooldown_time_seconds": 15,
            "allowed_fails": 1,
        },
        "rag": {
            "qdrant_url": "http://127.0.0.1:6333",
            "collection_name": "doc_knowledge",
            "embedding_model": "microsoft/harrier-oss-v1-0.6b",
            "rag_dir": "./rag",
            "docs_dir": "./rag",
        },
    }

    def __init__(self, config_dir: Path) -> None:
        """Salva la directory di configurazione."""
        self._dir = config_dir
        self._solver_cache: dict | None = None

    def _solver_cfg(self) -> dict:
        """Carica solver.toml in lazy load."""
        if self._solver_cache is None:
            path = self._dir / "solver.toml"
            if not path.exists():
                raise SolverConfigurationError(f"File solver.toml non trovato in '{self._dir}'.")
            self._solver_cache = toml_loads(path.read_text(encoding="utf-8"))
        return self._solver_cache

    def _section(self, section: str) -> dict:
        """Restituisce una sezione di solver.toml unita ai default."""
        merged = dict(self._DEFAULTS.get(section, {}))
        merged.update(self._solver_cfg().get(section, {}))
        return merged

    def load_providers(self) -> dict[str, Any]:
        """Carica providers.json."""
        path = self._dir / "providers.json"
        if not path.exists():
            raise SolverConfigurationError(f"File providers.json non trovato in '{self._dir}'.")
        return orjson_loads(path.read_bytes())

    def solver_max_tool_iterations(self) -> int:
        """Restituisce il massimo di iterazioni per i tool."""
        return int(self._section("solver")["max_tool_iterations"])

    def solver_max_retries(self) -> int:
        """Restituisce il numero di retry per task."""
        return int(self._section("solver")["max_retries"])

    def solver_temperature(self) -> float:
        """Restituisce la temperatura."""
        return float(self._section("solver")["temperature"])

    def qdrant_url(self) -> str:
        """Restituisce l'URL del database vettoriale Qdrant."""
        return str(self._section("rag")["qdrant_url"])

    def rag_collection_name(self) -> str:
        """Restituisce il nome della collezione di default in Qdrant."""
        return str(self._section("rag")["collection_name"])

    def embedding_model(self) -> str:
        """Restituisce il nome del modello di embedding configurato."""
        return str(self._section("rag")["embedding_model"])

    def load_rag_dir(self) -> Path:
        """Restituisce il percorso configurato della cartella documenti per RAG."""
        rag_section = self._section("rag")
        cfg_path = str(rag_section.get("rag_dir") or rag_section.get("docs_dir", "./rag"))
        p = Path(cfg_path)
        if not p.is_absolute():
            p = self._dir.parent / p
        return p

    def default_benchmark_path(self) -> Path | None:
        """Restituisce il percorso opzionale di default del benchmark da solver.toml."""
        raw_path = str(self._solver_cfg().get("run", {}).get("default_benchmark_path", ""))
        if not raw_path:
            return None
        p = Path(raw_path)
        if not p.is_absolute():
            p = self._dir.parent / p
        return p

    def dsn(self, key: str) -> str:
        """Restituisce il DSN per il database sandbox PostgreSQL (Porta 5433)."""
        default_dsn = "postgresql://solver:solver@127.0.0.1:5433/solver_sandbox"
        run_cfg = self._solver_cfg().get("run", {})
        toml_val = run_cfg.get(key) or run_cfg.get("db_dsn") or run_cfg.get("sandbox_dsn")
        return toml_val or default_dsn
