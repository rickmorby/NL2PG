"""Helper di dominio sui tipi di colonna e sulle trasformazioni di valore.

Predicati sui tipi dichiarati (intero, numerico, data, booleano) e
trasformazioni di valore (neutro, shift, scale, arrotondamento) condivise da
generazione righe e costruzione dello script INSERT.

:author: Riccardo Morabito
"""

from datetime import date, datetime, timedelta
from typing import Any

from bench.domain.models.data import ColumnSchema


def is_integer_type(data_type: str) -> bool:
    """True se il tipo dichiarato e' intero o serial."""
    lowered = data_type.lower()
    return "int" in lowered or "serial" in lowered


def is_numeric_type(data_type: str) -> bool:
    """True se il tipo dichiarato e' numerico non intero."""
    lowered = data_type.lower()
    return any(k in lowered for k in ("numeric", "decimal", "real", "double", "money", "float"))


def is_date_type(data_type: str) -> bool:
    """True se il tipo dichiarato e' data o timestamp."""
    lowered = data_type.lower()
    return "date" in lowered or "timestamp" in lowered


def is_bool_type(data_type: str) -> bool:
    """True se il tipo dichiarato e' booleano."""
    return "bool" in data_type.lower()


def neutral_value(column: ColumnSchema) -> Any:
    """Valore neutro di default per colonne non coperte dai template."""
    if column.nullable:
        return None
    if is_integer_type(column.data_type):
        return 0
    if is_numeric_type(column.data_type):
        return 0.0
    if is_bool_type(column.data_type):
        return False
    if is_date_type(column.data_type):
        return "2000-01-01"
    return ""


def shift_value(value: Any, column: ColumnSchema, delta: float) -> Any:
    """Sposta un valore numerico o di data di delta unita' (tollerante a T/spazio/Z)."""
    if is_date_type(column.data_type) and isinstance(value, str):
        normalized = value.strip().replace(" ", "T").rstrip("Z")
        try:
            dt = datetime.fromisoformat(normalized)
            dt = dt + timedelta(days=int(delta))
            if column.data_type.lower() == "date":
                return dt.date().isoformat()
            iso = dt.isoformat()
            if " " in value and "T" in iso:
                iso = iso.replace("T", " ", 1)
            return iso
        except (ValueError, OverflowError):
            try:
                parsed = date.fromisoformat(value.strip().split(" ")[0].split("T")[0])
                return (parsed + timedelta(days=int(delta))).isoformat()
            except (ValueError, OverflowError):
                return value
    if isinstance(value, (int, float)):
        return value + delta
    return value


def scale_value(value: Any, factor: float) -> Any:
    """Scala un valore numerico di un fattore (arrotondato a 2 decimali)."""
    if isinstance(value, (int, float)):
        return round(value * factor, 2)
    return value


def round_numeric(value: Any, column: ColumnSchema) -> Any:
    """Arrotonda i valori numerici non interi a 2 decimali."""
    if isinstance(value, float) and not is_integer_type(column.data_type):
        return round(value, 2)
    return value
