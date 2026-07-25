"""Classe base astratta per i DTO del benchmark.

:author: Riccardo Morabito
"""

from pydantic import BaseModel, ConfigDict


class AbstractDTO(BaseModel):
    """Classe base astratta per i DTO, basata su Pydantic.

    Tutti i DTO ereditano da questa classe e usano campi pubblici annotati
    con i tipi Python, seguendo le best practice Pydantic.
    La serializzazione/deserializzazione avviene tramite i metodi nativi
    ``model_dump()`` e ``model_validate()``.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
