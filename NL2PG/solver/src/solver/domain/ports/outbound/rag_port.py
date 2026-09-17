"""Porta outbound astratta per l'accesso RAG alla documentazione.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod


class DocRAGPort(ABC):
    """Porta astratta per l'interrogazione vettoriale/semantica dei file di documentazione."""

    @abstractmethod
    def search_documentation(self, query: str, top_k: int = 3) -> str:
        """Cerca nella documentazione aziendale i frammenti piu' rilevanti per la query."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Verifica che il database vettoriale sia raggiungibile e operativo."""

    @abstractmethod
    def indexed_chunks_count(self) -> int:
        """Restituisce il numero totale di chunk indicizzati nella collezione."""
