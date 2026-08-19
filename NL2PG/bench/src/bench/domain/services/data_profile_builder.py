"""Costruzione del profilo dati compatto mostrato agli agenti a valle.

``DataProfileBuilder`` sintetizza per ogni tabella conteggi, valori distinti,
campioni e min/max: il profilo e' deterministico (stesso seed -> stesso
profilo) e permette al QueryAgent di scrivere filtri su valori reali.

:author: Riccardo Morabito
"""

from typing import Any


class DataProfileBuilder:
    """Costruisce il profilo dati: conteggi, valori distinti, campioni, min/max."""

    @staticmethod
    def build(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        """Costruisce il profilo per ogni tabella dalle righe generate."""
        profile: dict[str, Any] = {}
        for table_name, table_rows in rows.items():
            columns: dict[str, Any] = {}
            for column_name in (table_rows[0].keys() if table_rows else []):
                values = [r[column_name] for r in table_rows]
                distinct = sorted({str(v) for v in values if v is not None})
                numeric = [v for v in values if isinstance(v, (int, float)) and v is not None]
                column_info: dict[str, Any] = {
                    "distinct": len(distinct),
                    "sample": distinct[:5],
                }
                if numeric:
                    column_info["min"] = min(numeric)
                    column_info["max"] = max(numeric)
                columns[column_name] = column_info
            profile[table_name] = {"row_count": len(table_rows), "columns": columns}
        return profile
