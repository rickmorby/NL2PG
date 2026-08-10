"""Servizio applicativo per i test di integrita' del sistema e health check dei provider LLM.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from logging import getLogger

from bench.domain.models.llm import SystemHealthReportDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort

_log = getLogger("bench.application.system_checker")


@dataclass
class ConfigCheckResult:
    """Esito del controllo di integrita' delle configurazioni."""

    bench_loaded: bool = True
    models_count: int = 0
    categories_count: int = 0
    config_hash: str = ""
    categories_hash: str = ""


class SystemCheckService:
    """Servizio applicativo per i controlli di diagnosi e configurazione."""

    def __init__(self, config: ConfigPort, llm: LLMGeneratorPort) -> None:
        """Inietta le porte outbound di configurazione ed LLM."""
        self._config = config
        self._llm = llm

    def check_configurations(self) -> ConfigCheckResult:
        """Carica le configurazioni e ne calcola gli hash di integrita'."""
        bench_cfg = self._config.load_bench()
        providers_cfg = self._config.load_providers()
        categories = self._config.load_categories()

        cfg_hash = self._config.config_hash(bench_cfg)
        cat_hash = self._config.config_hash({"categories": list(categories.keys())})

        return ConfigCheckResult(
            bench_loaded=bool(bench_cfg),
            models_count=len(providers_cfg.get("models", {})),
            categories_count=len(categories),
            config_hash=cfg_hash,
            categories_hash=cat_hash,
        )

    def check_llm_providers(self) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello di tutti i provider e modelli configurati."""
        return self._llm.check_all_providers()
