"""Servizio applicativo per i test di integrità del sistema e health check dei provider LLM.

:author: Riccardo Morabito
"""

from logging import getLogger

from bench.domain.models.llm import ConfigCheckResultDTO, SystemHealthReportDTO
from bench.domain.ports.inbound.system_checker_port import SystemCheckPort
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort

_log = getLogger("bench.application.system_checker")


class SystemCheckService(SystemCheckPort):
    """Servizio applicativo per i controlli di diagnosi e configurazione."""

    def __init__(self, config: ConfigPort, llm: LLMGeneratorPort) -> None:
        """Inietta le porte outbound di configurazione ed LLM."""
        self._config = config
        self._llm = llm

    def check_configurations(self) -> ConfigCheckResultDTO:
        """Carica le configurazioni e ne calcola gli hash di integrità."""
        providers_cfg = self._config.load_providers()
        categories = self._config.load_categories()

        cfg_hash = self._config.bench_hash()
        cat_hash = self._config.config_hash({"categories": list(categories.keys())})

        return ConfigCheckResultDTO(
            models_count=len(providers_cfg.get("models", {})),
            categories_count=len(categories),
            config_hash=cfg_hash,
            categories_hash=cat_hash,
        )

    def check_llm_providers(self, check_models: bool = True) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello di tutti i provider e modelli configurati."""
        return self._llm.check_all_providers(check_models=check_models)
