"""Servizio di dominio per il ripristino ed la sanificazione dell'SQL per PostgreSQL.

:author: Riccardo Morabito
"""

from re import DOTALL as re_DOTALL, IGNORECASE as re_IGNORECASE, search as re_search, sub as re_sub


class PostgresSQLRepair:
    """Servizio di dominio per il ripristino ed la sanificazione dell'SQL generato da LLM."""

    def repair(self, sql_text: str) -> str:
        """Applica la pipeline di riparazione deterministica al testo SQL per PostgreSQL."""
        if not sql_text:
            return ""

        sql = sql_text.strip()
        sql = self._strip_markdown_fences(sql)
        sql = self._fix_escaped_quotes(sql)
        sql = self._fix_trailing_commas(sql)
        sql = self._ensure_semicolon(sql)
        return sql.strip()

    def _strip_markdown_fences(self, sql: str) -> str:
        """Rimuove eventuali involucri di codice Markdown."""
        if "```" in sql:
            pattern = r"```(?:sql|postgres)?\s*(.*?)\s*```"
            m = re_search(pattern, sql, flags=re_DOTALL | re_IGNORECASE)
            if m:
                return m.group(1).strip()
            sql = re_sub(r"^```[a-zA-Z]*\n?", "", sql)
            sql = re_sub(r"\n?```$", "", sql).strip()
        return sql

    def _fix_escaped_quotes(self, sql: str) -> str:
        r"""Converte l'escape errato C/JS (\') nel raddoppio apici Postgres ('')."""
        return re_sub(r"(?<=\w)\\'(?=\w)", "''", sql)

    def _fix_trailing_commas(self, sql: str) -> str:
        """Rimuove le virgole pendenti prima di chiusura parentesi o clausole principali."""
        pattern = r",\s*(\)|FROM\b|WHERE\b|GROUP\s+BY\b|ORDER\s+BY\b|HAVING\b)"
        return re_sub(pattern, r" \1", sql, flags=re_IGNORECASE)

    def _ensure_semicolon(self, sql: str) -> str:
        """Assicura che il comando o script SQL termini con punto e virgola ';'."""
        cleaned = sql.rstrip()
        if cleaned and not cleaned.endswith(";"):
            return f"{cleaned};"
        return cleaned
