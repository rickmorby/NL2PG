"""Builder per messaggi di errore arricchiti da feedback LLM."""

from typing import Any

from psycopg.errors import Error as PgError


class ErrorFeedbackBuilder:
    """Costruisce messaggi con DETAIL/HINT di Postgres e sample del profilo."""

    def from_pg_error(self, prefix: str, error: PgError | Exception) -> str:
        """Arricchisce errore Postgres con diag."""
        base = f"{prefix}: {error}"
        diag = getattr(error, "diag", None)
        if diag is None:
            return base
        parts: list[str] = [base]
        detail = getattr(diag, "message_detail", None)
        hint = getattr(diag, "message_hint", None)
        table = getattr(diag, "table_name", None)
        column = getattr(diag, "column_name", None)
        constraint = getattr(diag, "constraint_name", None)
        if detail:
            parts.append(f"DETAIL: {detail}")
        if hint:
            parts.append(f"HINT: {hint}")
        if table:
            parts.append(f"Tabella: {table}")
        if column:
            parts.append(f"Colonna: {column}")
        if constraint:
            parts.append(f"Vincolo: {constraint}")
        return " | ".join(parts)

    def for_pool(self, table: str, column: str, pool: list[Any], fk_count: int) -> str:
        """Messaggio per pool non stringa."""
        return (
            f"Validazione pool fallita su {table}.{column} con {pool}: "
            f'il pool richiede stringhe quotate ["1","2"] non interi. '
            f"Tabella ha {fk_count} FK."
        )

    def for_per_parent(self, table: str, found: int, fks: list[str]) -> str:
        """Messaggio per per_parent_rows invalido."""
        return (
            f"'per_parent_rows' su {table} richiede 1 FK, trovate {found} "
            f"({', '.join(fks)}). Rimosso, usa explicit."
        )

    def for_mutation(self, tables: list[str], distinct: dict[str, Any]) -> str:
        """Messaggio per query insensibile alla mutazione."""
        use = {k: v for k, v in distinct.items() if not self._is_key_column(k)}
        if not use:
            use = distinct
        sample = ", ".join(f"{k}={v}" for k, v in list(use.items())[:2])
        return (
            f"Query insensibile su {', '.join(tables)}: risultato identico "
            f"prima/dopo mutazione. Aggiungi WHERE su colonna mutabile "
            f"(non PK) con distinct>1, es. nome/stato. Sample: {sample}."
        )

    @staticmethod
    def _is_key_column(qualified: str) -> bool:
        """Riconosce i nomi tipici di chiavi PK/FK (id, id_x, x_id) da escludere."""
        column = qualified.rsplit(".", 1)[-1].lower()
        return column == "id" or column.startswith("id_") or column.endswith("_id")

    def for_empty_result(self, where: str | None, distinct: dict[str, Any]) -> str:
        """Messaggio per query con 0 righe."""
        sample = ", ".join(f"{k}={v}" for k, v in list(distinct.items())[:2])
        return (
            f"Query vuota 0 righe con {where}. Valore non in profile. "
            f"Sample: {sample}. Usa valore da preview."
        )

    def for_group_by(self, col: str, pg_msg: str) -> str:
        """Messaggio per GROUP BY mancante."""
        return f"GROUP BY mancante per {col}. {pg_msg}."
