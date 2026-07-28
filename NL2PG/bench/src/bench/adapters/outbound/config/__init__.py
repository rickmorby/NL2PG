"""Adapter per caricamento configurazione da filesystem.

:author: Riccardo Morabito
"""

from hashlib import sha256
from json import dumps, loads
from os import environ
from pathlib import Path
from tomllib import load as toml_load

from bench.domain.models.category import CategoryDTO
from bench.domain.ports.outbound.config_port import ConfigPort


class ConfigAdapter(ConfigPort):
    """Carica providers, bench, categorie e DSN da file JSON/TOML o ambiente."""

    def __init__(self, config_dir: Path) -> None:
        """Salva il percorso della directory di configurazione."""
        self._dir = config_dir

    def load_providers(self) -> dict:
        """Restituisce il contenuto di providers.json come dict."""
        return loads((self._dir / "providers.json").read_text(encoding="utf-8"))

    def load_bench(self) -> dict:
        """Restituisce il contenuto di bench.toml come dict, o dict vuoto se assente."""
        path = self._dir / "bench.toml"
        if not path.exists():
            return {}
        with open(path, "rb") as f:
            return toml_load(f)

    def load_categories(self) -> dict[str, CategoryDTO]:
        """Restituisce un dict {id: CategoryDTO} dal file categories.json."""
        data = loads((self._dir / "categories.json").read_text(encoding="utf-8"))
        return {c["id"]: CategoryDTO(**c) for c in data["categories"]}

    def dsn(self, key: str) -> str:
        """Restituisce il DSN dalla variabile d'ambiente o dal fallback bench.toml."""
        env_map = {"db_dsn": "BENCH_DB_DSN", "meta_dsn": "BENCH_META_DSN"}
        env_var = env_map.get(key, "BENCH_DB_DSN")
        bench = self.load_bench()
        return environ.get(env_var, bench.get("run", {}).get(key, ""))

    def config_hash(self, cfg: dict) -> str:
        """Calcola l'hash SHA256 di un dict di configurazione."""
        payload = dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
        return sha256(payload.encode("utf-8")).hexdigest()[:16]