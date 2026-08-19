"""Porta per il caricamento della configurazione del benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod

from bench.domain.models.category import CategoryDTO


class ConfigPort(ABC):
    """Interfaccia per caricare configurazioni da filesystem."""

    @abstractmethod
    def load_providers(self) -> dict:
        """Carica providers.json con la configurazione dei modelli LLM."""

    @abstractmethod
    def load_categories(self) -> dict[str, CategoryDTO]:
        """Carica categories.json e restituisce un dict {id: CategoryDTO}."""

    @abstractmethod
    def dsn(self, key: str) -> str:
        """Restituisce il DSN per la connessione da bench.toml o il default di fallback."""

    @abstractmethod
    def bench_hash(self) -> str:
        """Hash SHA256 del contenuto di bench.toml per identificare la run."""

    @abstractmethod
    def retry_max_per_node(self) -> int:
        """Tentativi massimi per nodo della pipeline ([retry].max_per_node)."""

    @abstractmethod
    def hardening_max_rounds(self) -> int:
        """Numero massimo di round di hardening ([hardening].max_rounds)."""

    @abstractmethod
    def calibration_runs(self) -> int:
        """Numero di run di calibration ([calibration].runs)."""

    @abstractmethod
    def calibration_temperature(self) -> float:
        """Temperatura di sampling per la calibration ([calibration].temperature)."""

    @abstractmethod
    def recursion_limit(self) -> int:
        """Limite di ricorsione del grafo orchestratore ([orchestrator].recursion_limit)."""

    @abstractmethod
    def critic_weights(self) -> dict[str, float]:
        """Pesi delle dimensioni valutate dal critic ([critic].weights)."""

    @abstractmethod
    def critic_high_threshold(self) -> float:
        """Soglia alta del critic per il passaggio diretto ([thresholds].critic_high)."""

    @abstractmethod
    def judge_max_regens(self) -> int:
        """Numero massimo di rigenerazioni del judge ([judge].max_regens)."""

    @abstractmethod
    def cli_max_consecutive_failures(self) -> int:
        """Fallimenti consecutivi che attivano il circuit breaker (sezione [cli])."""

    @abstractmethod
    def cli_category_failure_warning(self) -> int:
        """Soglia di fallimenti per il warning di categoria ([cli].category_failure_warning)."""

    @abstractmethod
    def data_nature_ranges(self) -> dict[str, tuple[int, int]]:
        """Range di righe per natura di tabella ([data].nature_ranges)."""

    @abstractmethod
    def data_max_rows_per_table(self) -> int:
        """Massimo righe per tabella materializzabile ([data].max_rows_per_table)."""

    @abstractmethod
    def data_max_total_rows(self) -> int:
        """Massimo righe totali per task ([data].max_total_rows)."""

    @abstractmethod
    def data_batch_size(self) -> int:
        """Dimensione dei batch INSERT ([data].batch_size)."""

    @abstractmethod
    def data_null_rate(self) -> float:
        """Tasso di NULL iniettati su colonne nullable ([data].null_rate)."""

    @abstractmethod
    def data_dup_rate(self) -> float:
        """Tasso di righe duplicate per tabella ([data].dup_rate)."""

    @abstractmethod
    def data_outlier_rate(self) -> float:
        """Tasso di outlier entro i limiti dichiarati ([data].outlier_rate)."""

    @abstractmethod
    def data_preview_size(self) -> int:
        """Numero di righe reali mostrate nel profilo dati ([data].preview_size)."""

    @abstractmethod
    def config_hash(self, cfg: dict) -> str:
        """Calcola l'hash SHA256 di una configurazione per identificare la run."""
