"""Modulo base per i DTO del benchmark.

:author: Riccardo Morabito
"""

from abc import ABC, abstractmethod
from json import dumps
from typing import Any
from pydantic import BaseModel, ConfigDict


class DTOInterface(ABC):
    """Interfaccia per la serializzazione dei DTO in dizionario e JSON."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Converte il DTO in dizionario."""
        pass

    @abstractmethod
    def to_json(self) -> str:
        """Converte il DTO in stringa JSON."""
        pass


class AbstractDTO(BaseModel, DTOInterface, ABC):
    """Classe base astratta che genera i metodi get_* e set_* all'avvio."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    def __init_subclass__(cls, **kwargs: Any):
        """Hook nativo di Python invocato quando viene definita una sottoclasse DTO."""
        super().__init_subclass__(**kwargs)

        p_attrs = getattr(cls, "__private_attributes__", {})
        for attr_name in p_attrs:
            if attr_name.startswith("_"):
                field_name = attr_name[1:]
                getter_name = f"get_{field_name}"
                setter_name = f"set_{field_name}"

                if not hasattr(cls, getter_name):
                    setattr(cls, getter_name, cls._create_getter(attr_name))

                if not hasattr(cls, setter_name):
                    setattr(cls, setter_name, cls._create_setter(attr_name))

    @classmethod
    def _create_getter(cls, attr_name: str):
        """Crea la funzione getter per un attributo privato."""
        def _getter(self: Any) -> Any:
            p_priv = getattr(self, "__pydantic_private__", {}) or {}
            return p_priv.get(attr_name, None)

        return _getter

    @classmethod
    def _create_setter(cls, attr_name: str):
        """Crea la funzione setter per un attributo privato."""
        def _setter(self: Any, value: Any) -> None:
            p_priv = getattr(self, "__pydantic_private__", {}) or {}
            p_priv[attr_name] = value

        return _setter

    def __init__(self, **data: Any):
        """Inizializza la sottoclasse popolando gli attributi privati."""
        super().__init__()
        p_attrs = getattr(self.__class__, "__private_attributes__", {})
        for k, v in data.items():
            priv_k = f"_{k}" if not k.startswith("_") else k
            if priv_k in p_attrs:
                setter_name = f"set_{priv_k[1:]}"
                if hasattr(self, setter_name):
                    getattr(self, setter_name)(v)

    def __getattr__(self, item: str) -> Any:
        """Blocca l'accesso diretto ai campi pubblici suggerendo l'uso dei getter."""
        if not item.startswith("_"):
            getter_name = f"get_{item}"
            if hasattr(self.__class__, getter_name):
                raise AttributeError(
                    f"L'accesso diretto al campo '{item}' è proibito. "
                    f"Utilizzare {getter_name}() al suo posto."
                )

        raise AttributeError(
            f"L'oggetto '{self.__class__.__name__}' non possiede l'attributo '{item}'."
        )

    def to_dict(self) -> dict[str, Any]:
        """Restituisce il DTO come dizionario leggendo i getter generati."""
        res: dict[str, Any] = {}
        p_attrs = getattr(self.__class__, "__private_attributes__", {})
        for attr_name in p_attrs:
            if attr_name.startswith("_"):
                public_name = attr_name[1:]
                getter_name = f"get_{public_name}"
                if hasattr(self, getter_name):
                    val = getattr(self, getter_name)()
                    if hasattr(val, "to_dict"):
                        res[public_name] = val.to_dict()
                    elif isinstance(val, list):
                        res[public_name] = [
                            item.to_dict() if hasattr(item, "to_dict") else item for item in val
                        ]
                    else:
                        res[public_name] = val
        return res

    def to_json(self) -> str:
        """Restituisce il DTO come stringa JSON."""
        return dumps(self.to_dict(), ensure_ascii=False)
