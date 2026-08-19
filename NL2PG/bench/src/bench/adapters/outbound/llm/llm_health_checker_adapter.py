"""Adattatore outbound per la diagnosi HTTP multilivello dei provider e modelli LLM.

:author: Riccardo Morabito
"""

from http import HTTPStatus
from typing import Any

from httpx import Client, HTTPError

from bench.domain.models.llm import (
    ModelHealthDTO,
    ProviderHealthDTO,
    SystemHealthReportDTO,
)


class LLMHealthCheckerAdapter:
    """Adattatore per la diagnosi di connettività dei provider e fruibilità dei modelli."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Inizializza l'adattatore con la configurazione dei modelli ed i ruoli."""
        self._config = config

    def check_all_providers(self, check_models: bool = True) -> SystemHealthReportDTO:
        """Esegue la diagnosi multilivello dei pool e dei modelli fisici univoci."""
        pools_grouped = self._group_physical_models()
        provider_reports: list[ProviderHealthDTO] = []
        total_physical_models = 0
        healthy_models_count = 0
        reachable_providers_count = 0

        with Client(timeout=10.0) as client:
            for pool_name, pool_data in pools_grouped.items():
                target_models = pool_data["models"]
                p_report = self._check_provider_endpoint(
                    client, pool_name, pool_data["base_url"], pool_data["api_key"]
                )
                total_physical_models += len(target_models)

                if p_report.is_reachable:
                    reachable_providers_count += 1
                    model_reports = []
                    for t_model, data in target_models.items():
                        sorted_roles = sorted(list(data["roles"]))
                        if check_models:
                            m_report = self._check_model_health(
                                client=client,
                                model_info=(data["model_ids"][0], t_model, sorted_roles),
                                endpoint=(pool_data["base_url"], pool_data["api_key"]),
                            )
                            if m_report.is_healthy:
                                healthy_models_count += 1
                        else:
                            m_report = ModelHealthDTO(
                                model_id=data["model_ids"][0],
                                target_model=t_model,
                                roles=sorted_roles,
                                is_healthy=True,
                                error_message="",
                            )
                        model_reports.append(m_report)
                    p_report.models = model_reports
                else:
                    p_report.models = [
                        ModelHealthDTO(
                            model_id=data["model_ids"][0],
                            target_model=t_model,
                            roles=sorted(list(data["roles"])),
                            is_healthy=False,
                            error_message="Provider non raggiungibile o autenticazione fallita.",
                        )
                        for t_model, data in target_models.items()
                    ]
                provider_reports.append(p_report)

        return SystemHealthReportDTO(
            total_providers=len(pools_grouped),
            reachable_providers=reachable_providers_count,
            total_models=total_physical_models,
            healthy_models=healthy_models_count if check_models else total_physical_models,
            providers=provider_reports,
        )

    def _group_physical_models(self) -> dict[str, dict[str, Any]]:
        """Raggruppa i modelli fisici e i loro ruoli per pool gateway."""
        models = self._config.get("models", {})
        chains = self._config.get("chains", {})

        mid_roles: dict[str, list[str]] = {}
        for role, m_list in chains.items():
            for m_id in m_list:
                mid_roles.setdefault(m_id, []).append(role)

        pools_grouped: dict[str, dict[str, Any]] = {}
        for m_id, m_info in models.items():
            pool = m_info.get("pool", m_id)
            target_model = m_info.get("model", "")
            group = pools_grouped.setdefault(
                pool,
                {
                    "provider": m_info.get("provider", "openai"),
                    "base_url": m_info.get("base_url", "https://api.openai.com/v1"),
                    "api_key": m_info.get("api_key", ""),
                    "models": {},
                },
            )
            entry = group["models"].setdefault(
                target_model,
                {"model_ids": [], "roles": set(), "info": m_info},
            )
            entry["model_ids"].append(m_id)
            entry["roles"].update(mid_roles.get(m_id, []))

        return pools_grouped

    def _check_provider_endpoint(
        self, client: Client, provider_name: str, base_url: str, api_key: str
    ) -> ProviderHealthDTO:
        """Invia una richiesta GET /v1/models per verificare se il provider e' raggiungibile."""
        clean_url = base_url.rstrip("/")
        models_url = f"{clean_url}/models" if not clean_url.endswith("/models") else clean_url
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            resp = client.get(models_url, headers=headers)
            if resp.status_code == HTTPStatus.OK:
                return ProviderHealthDTO(
                    provider_name=provider_name,
                    base_url=base_url,
                    is_reachable=True,
                    error_message="",
                )
            return ProviderHealthDTO(
                provider_name=provider_name,
                base_url=base_url,
                is_reachable=False,
                error_message=f"HTTP {resp.status_code}: {resp.text[:120]}",
            )
        except (HTTPError, OSError, ValueError, RuntimeError) as e:
            return ProviderHealthDTO(
                provider_name=provider_name,
                base_url=base_url,
                is_reachable=False,
                error_message=f"Errore di connessione: {e}",
            )

    def _check_model_health(
        self,
        client: Client,
        model_info: tuple[str, str, list[str]],
        endpoint: tuple[str, str],
    ) -> ModelHealthDTO:
        """Invia un ping di completamento per verificare la reale fruibilità del modello."""
        model_id, target_model, roles = model_info
        base_url, api_key = endpoint

        clean_url = base_url.rstrip("/")
        comp_url = f"{clean_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }

        try:
            resp = client.post(comp_url, headers=headers, json=payload)
            if resp.status_code == HTTPStatus.OK:
                return ModelHealthDTO(
                    model_id=model_id,
                    target_model=target_model,
                    roles=roles,
                    is_healthy=True,
                    error_message="",
                )
            return ModelHealthDTO(
                model_id=model_id,
                target_model=target_model,
                roles=roles,
                is_healthy=False,
                error_message=f"HTTP {resp.status_code}: {resp.text[:120]}",
            )
        except (HTTPError, OSError, ValueError, RuntimeError) as e:
            return ModelHealthDTO(
                model_id=model_id,
                target_model=target_model,
                roles=roles,
                is_healthy=False,
                error_message=f"Errore ping completamento: {e}",
            )
