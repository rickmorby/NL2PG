"""Adapter per caricamento configurazione da filesystem.

:author: Riccardo Morabito
"""

from hashlib import sha256
from pathlib import Path
from tomllib import loads as toml_loads
from typing import ClassVar

from orjson import OPT_SORT_KEYS, dumps as orjson_dumps, loads as orjson_loads

from bench.domain.exceptions import (
    ConfigurationMissingFieldError,
    ProviderConfigError,
)
from bench.domain.models.category import CategoryDTO
from bench.domain.ports.outbound.config_port import ConfigPort


class ConfigAdapter(ConfigPort):
    """Carica providers, bench, categorie e DSN da file JSON/TOML.

    bench.toml viene letto e parsato una sola volta (lazy load con cache):
    l'istanza è condivisa come singleton dalla Composition Root e i getter
    tipizzati espongono i valori senza esporre la struttura interna del file.
    I valori di default sono centralizzati in ``_DEFAULTS`` (unica fonte di verità).
    """

    _DEFAULTS: ClassVar[dict[str, dict[str, object]]] = {
        "retry": {"max_per_node": 3},
        "hardening": {"max_rounds": 3},
        "calibration": {"runs": 3, "temperature": 0.9},
        "orchestrator": {"recursion_limit": 150},
        "critic": {"weights": {}},
        "thresholds": {"critic_high": 6.0},
        "judge": {"max_regens": 2},
        "data": {
            "nature_ranges": {
                "lookup": [5, 50],
                "dimension": [100, 800],
                "fact": [300, 3000],
            },
            "max_rows_per_table": 3000,
            "max_total_rows": 30000,
            "batch_size": 100,
            "null_rate": 0.05,
            "dup_rate": 0.03,
            "outlier_rate": 0.02,
            "preview_size": 8,
        },
        "cli": {"max_consecutive_failures": 5, "category_failure_warning": 5},
    }

    def __init__(self, config_dir: Path) -> None:
        """Salva il percorso della directory di configurazione."""
        self._dir = config_dir
        self._bench_cache: dict | None = None

    def _bench(self) -> dict:
        """Carica bench.toml una sola volta (lazy load) e lo restituisce come dict."""
        if self._bench_cache is None:
            path = self._dir / "bench.toml"
            if not path.exists():
                msg = (
                    f"File di configurazione bench.toml non trovato in '{self._dir}'. "
                    "Il file andrebbe configurato per definire i parametri del benchmark."
                )
                payload = {"path": str(path), "file": "bench.toml"}
                raise ConfigurationMissingFieldError(msg, payload=payload)
            self._bench_cache = toml_loads(path.read_text(encoding="utf-8"))
        return self._bench_cache

    def _section(self, section: str) -> dict:
        """Restituisce una sezione di bench.toml unita ai default centralizzati."""
        merged = dict(self._DEFAULTS.get(section, {}))
        merged.update(self._bench().get(section, {}))
        return merged

    def bench_hash(self) -> str:
        """Calcola l'hash SHA256 del contenuto di bench.toml per identificare la run."""
        return self.config_hash(self._bench())

    def retry_max_per_node(self) -> int:
        """Restituisce il numero massimo di tentativi per nodo della pipeline."""
        return int(self._section("retry")["max_per_node"])

    def hardening_max_rounds(self) -> int:
        """Restituisce il numero massimo di round di hardening."""
        return int(self._section("hardening")["max_rounds"])

    def calibration_runs(self) -> int:
        """Restituisce il numero di run di calibration."""
        return int(self._section("calibration")["runs"])

    def calibration_temperature(self) -> float:
        """Restituisce la temperatura di sampling per la calibration."""
        return float(self._section("calibration")["temperature"])

    def recursion_limit(self) -> int:
        """Restituisce il limite di ricorsione del grafo orchestratore."""
        return int(self._section("orchestrator")["recursion_limit"])

    def critic_weights(self) -> dict[str, float]:
        """Restituisce i pesi delle dimensioni valutate dal critic."""
        return dict(self._section("critic")["weights"])

    def critic_high_threshold(self) -> float:
        """Restituisce la soglia alta del critic per il passaggio diretto."""
        return float(self._section("thresholds")["critic_high"])

    def judge_max_regens(self) -> int:
        """Restituisce il numero massimo di rigenerazioni del judge."""
        return int(self._section("judge")["max_regens"])

    def cli_max_consecutive_failures(self) -> int:
        """Restituisce i fallimenti consecutivi che attivano il circuit breaker."""
        return int(self._section("cli")["max_consecutive_failures"])

    def cli_category_failure_warning(self) -> int:
        """Restituisce la soglia di fallimenti per il warning di categoria."""
        return int(self._section("cli")["category_failure_warning"])

    def data_nature_ranges(self) -> dict[str, tuple[int, int]]:
        """Restituisce i range di righe per natura di tabella."""
        raw = dict(self._section("data")["nature_ranges"])
        return {k: (int(v[0]), int(v[1])) for k, v in raw.items()}

    def data_max_rows_per_table(self) -> int:
        """Restituisce il massimo di righe per tabella materializzabile."""
        return int(self._section("data")["max_rows_per_table"])

    def data_max_total_rows(self) -> int:
        """Restituisce il massimo di righe totali per task."""
        return int(self._section("data")["max_total_rows"])

    def data_batch_size(self) -> int:
        """Restituisce la dimensione dei batch INSERT."""
        return int(self._section("data")["batch_size"])

    def data_null_rate(self) -> float:
        """Restituisce il tasso di NULL su colonne nullable."""
        return float(self._section("data")["null_rate"])

    def data_dup_rate(self) -> float:
        """Restituisce il tasso di righe duplicate."""
        return float(self._section("data")["dup_rate"])

    def data_outlier_rate(self) -> float:
        """Restituisce il tasso di outlier entro i limiti dichiarati."""
        return float(self._section("data")["outlier_rate"])

    def data_preview_size(self) -> int:
        """Restituisce il numero di righe reali mostrate nel profilo dati."""
        return int(self._section("data")["preview_size"])

    def load_providers(self) -> dict:
        """Restituisce il contenuto di providers.json come dict."""
        path = self._dir / "providers.json"
        if not path.exists():
            msg = (
                f"File di configurazione providers.json non trovato in '{self._dir}'. "
                "Il file andrebbe configurato per il corretto funzionamento dei provider LLM."
            )
            raise ProviderConfigError(msg, payload={"path": str(path)})
        return orjson_loads(path.read_bytes())

    def load_categories(self) -> dict[str, CategoryDTO]:
        """Restituisce un dict {id: CategoryDTO} dal file categories.json."""
        path = self._dir / "categories.json"
        if not path.exists():
            msg = (
                f"File di configurazione categories.json non trovato in '{self._dir}'. "
                "Il file andrebbe configurato per caricare le categorie del benchmark."
            )
            payload = {"path": str(path), "file": "categories.json"}
            raise ConfigurationMissingFieldError(msg, payload=payload)
        data = orjson_loads(path.read_bytes())
        return {c["id"]: CategoryDTO(**c) for c in data["categories"]}

    def dsn(self, key: str) -> str:
        """Restituisce il DSN da bench.toml o il valore di default se assente.

        :param key: Chiave del DSN richiesta ('db_dsn', 'sandbox_dsn' o 'meta_dsn').
        :return: Stringa di connessione DSN PostgreSQL.
        """
        default_map = {
            "db_dsn": "postgresql://bench:bench@127.0.0.1:5432/bench_sandbox",
            "sandbox_dsn": "postgresql://bench:bench@127.0.0.1:5432/bench_sandbox",
            "meta_dsn": "postgresql://bench:bench@127.0.0.1:5432/bench_meta",
        }

        run_cfg = self._bench().get("run", {})
        toml_val = run_cfg.get(key)
        if not toml_val and key in ("db_dsn", "sandbox_dsn"):
            toml_val = run_cfg.get("db_dsn") or run_cfg.get("sandbox_dsn")

        if toml_val:
            return toml_val
        if key in default_map:
            return default_map[key]
        msg = f"La chiave DSN '{key}' non è prevista nella configurazione."
        raise ConfigurationMissingFieldError(
            msg,
            payload={"key": key, "file": "bench.toml"},
        )

    def config_hash(self, cfg: dict) -> str:
        """Calcola l'hash SHA256 di un dict di configurazione."""
        payload = orjson_dumps(cfg, option=OPT_SORT_KEYS)
        return sha256(payload).hexdigest()[:16]
