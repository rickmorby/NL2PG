"""Classe base astratta per i DTO del benchmark.

:author: Riccardo Morabito
"""

from pydantic import BaseModel, ConfigDict


class AbstractDTO(BaseModel):
    """Classe base Pydantic per i DTO con campi pubblici, model_dump() e model_validate()."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
