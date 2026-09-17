"""Modulo DTO di base immutabile per il dominio di solver.

:author: Riccardo Morabito
"""

from typing import Any
from pydantic import BaseModel, ConfigDict


class AbstractDTO(BaseModel):
    """Classe base astratta per tutti i DTO del sistema solver."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    def to_dict(self) -> dict[str, Any]:
        """Converte l'istanza DTO in dizionario Python nativo."""
        return self.model_dump()
