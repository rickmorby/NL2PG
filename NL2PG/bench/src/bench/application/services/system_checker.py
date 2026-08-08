"""Servizio applicativo per i test di integrita' del sistema e health check dei provider LLM.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from logging import getLogger

from bench.domain.models.nlp import JudgeDTO
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


@dataclass
class ProviderCheckResult:
    """Esito della verifica di connettivita' del provider LLM."""

    success: bool = True
    model_used: str = ""
    error: str = ""


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

    def check_llm_providers(self) -> ProviderCheckResult:
        """Invia un prompt di test alla catena LLM per verificare la connettivita'."""
        try:
            res = self._llm.call_model(
                role="default",
                prompt='Rispondi esclusivamente con un oggetto JSON: {"verdict": "hard"}',
                schema=JudgeDTO,
            )
            return ProviderCheckResult(success=True, model_used=self._extract_model_used(res))
        except Exception as e:
            _log.error("Verifica provider LLM fallita: %s", e)
            return ProviderCheckResult(success=False, error=str(e))

    @staticmethod
    def _extract_model_used(res: object) -> str:
        """Estrae in modo sicuro il modello utilizzato dal risultato dell'invocazione."""
        return getattr(res, "model_used", "")
