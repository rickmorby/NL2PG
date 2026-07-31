"""Porta astratta outbound per la persistenza ed il tracciamento dei metadati e dei task.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from bench.domain.models.state import TaskStateDTO


class MetaRepositoryPort(ABC):
    """Porta outbound per le operazioni di persistenza e deduplicazione su bench_meta."""

    @abstractmethod
    def new_run(self, config_hash: str, categories_hash: str) -> str:
        """Registra una nuova esecuzione e restituisce l'identificativo univoco run_id."""
        pass

    @abstractmethod
    def is_spec_duplicated(self, category: str, spec_hash: str) -> bool:
        """Verifica se una specifica è già presente per la categoria in stato accepted/pending."""
        pass

    @abstractmethod
    def get_top_k_tasks(self, category: str, k: int) -> list[str]:
        """Restituisce i task_id dei migliori k task accettati per la categoria specificata."""
        pass

    @abstractmethod
    def save_task(self, run_id: str, state: TaskStateDTO) -> None:
        """Esegue l'upsert dello stato di un task nella tabella bench_meta.tasks."""
        pass

