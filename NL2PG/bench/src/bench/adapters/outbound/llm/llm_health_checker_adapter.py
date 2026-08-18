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
        """Esegue la diagnosi multilivello dei provider e dei modelli fisici univoci."""
        providers_grouped = self._group_physical_models()
        provider_reports: list[ProviderHealthDTO] = []
        total_physical_models = 0
        healthy_models_count = 0
        reachable_providers_count = 0

        with Client(timeout=10.0) as client:
            for (p_name, base_url, api_key), target_models in providers_grouped.items():
                p_report, server_models = self._check_provider_endpoint(
                    client, p_name, base_url, api_key
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
                                endpoint=(base_url, api_key),
                                server_models=server_models,
                            )
                            if m_report.is_healthy:
                                healthy_models_count += 1
                        else:
                            m_report = ModelHealthDTO(
                                model_id=data["model_ids"][0],
                                target_model=t_model,
                                roles=sorted_roles,
                                is_available_on_server=True,
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
                            is_available_on_server=False,
                            is_healthy=False,
                            error_message="Provider non raggiungibile o autenticazione fallita.",
                        )
                        for t_model, data in target_models.items()
                    ]
                provider_reports.append(p_report)

        return SystemHealthReportDTO(
            total_providers=len(providers_grouped),
            reachable_providers=reachable_providers_count,
            total_models=total_physical_models,
            healthy_models=healthy_models_count if check_models else total_physical_models,
            providers=provider_reports,
        )

    def _group_physical_models(self) -> dict[tuple[str, str, str], dict[str, dict[str, Any]]]:
        """Raggruppa i modelli fisici e i loro ruoli per provider."""
        models = self._config.get("models", {})
        chains = self._config.get("chains", {})

        mid_roles: dict[str, list[str]] = {}
        for role, m_list in chains.items():
            for m_id in m_list:
                if m_id not in mid_roles:
                    mid_roles[m_id] = []
                mid_roles[m_id].append(role)

        providers_grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}

        for m_id, m_info in models.items():
            p_name = m_info.get("provider", "openai")
            base_url = m_info.get("base_url", "https://api.openai.com/v1")
            api_key = m_info.get("api_key", "")
            target_model = m_info.get("model", "")
            roles = mid_roles.get(m_id, [])

            p_key = (p_name, base_url, api_key)
            if p_key not in providers_grouped:
                providers_grouped[p_key] = {}

            if target_model not in providers_grouped[p_key]:
                providers_grouped[p_key][target_model] = {
                    "model_ids": [],
                    "roles": set(),
                    "info": m_info,
                }
            providers_grouped[p_key][target_model]["model_ids"].append(m_id)
            providers_grouped[p_key][target_model]["roles"].update(roles)

        return providers_grouped

    def _check_provider_endpoint(
        self, client: Client, provider_name: str, base_url: str, api_key: str
    ) -> tuple[ProviderHealthDTO, set[str]]:
        """Invia una richiesta GET /v1/models per verificare se il provider e' raggiungibile."""
        clean_url = base_url.rstrip("/")
        models_url = f"{clean_url}/models" if not clean_url.endswith("/models") else clean_url
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            resp = client.get(models_url, headers=headers)
            if resp.status_code == HTTPStatus.OK:
                data = resp.json()
                server_model_ids = {
                    item.get("id")
                    for item in data.get("data", [])
                    if isinstance(item, dict) and item.get("id")
                }
                return (
                    ProviderHealthDTO(
                        provider_name=provider_name,
                        base_url=base_url,
                        is_reachable=True,
                        error_message="",
                    ),
                    server_model_ids,
                )
            return (
                ProviderHealthDTO(
                    provider_name=provider_name,
                    base_url=base_url,
                    is_reachable=False,
                    error_message=f"HTTP {resp.status_code}: {resp.text[:120]}",
                ),
                set(),
            )
        except (HTTPError, OSError, ValueError, RuntimeError) as e:
            return (
                ProviderHealthDTO(
                    provider_name=provider_name,
                    base_url=base_url,
                    is_reachable=False,
                    error_message=f"Errore di connessione: {e}",
                ),
                set(),
            )

    def _check_model_health(
        self,
        client: Client,
        model_info: tuple[str, str, list[str]],
        endpoint: tuple[str, str],
        server_models: set[str],
    ) -> ModelHealthDTO:
        """Invia un ping di completamento per verificare la reale fruibilità del modello."""
        model_id, target_model, roles = model_info
        base_url, api_key = endpoint
        is_available = bool(
            not server_models
            or target_model in server_models
            or any(target_model in m for m in server_models)
        )

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
                    is_available_on_server=is_available,
                    is_healthy=True,
                    error_message="",
                )
            return ModelHealthDTO(
                model_id=model_id,
                target_model=target_model,
                roles=roles,
                is_available_on_server=is_available,
                is_healthy=False,
                error_message=f"HTTP {resp.status_code}: {resp.text[:120]}",
            )
        except (HTTPError, OSError, ValueError, RuntimeError) as e:
            return ModelHealthDTO(
                model_id=model_id,
                target_model=target_model,
                roles=roles,
                is_available_on_server=is_available,
                is_healthy=False,
                error_message=f"Errore ping completamento: {e}",
            )
