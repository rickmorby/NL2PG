"""Modulo per la validazione di sicurezza ed anti-cheating delle query SQL.

Impedisce tentativi di accesso a cataloghi di sistema (pg_catalog, information_schema),
cronologia delle query eseguite (pg_stat_statements, pg_stat_activity), funzioni di file-system
e schemi di altri task.

:author: Riccardo Morabito
"""

from sqlglot import exp

from solver.domain.exceptions import SandboxSolverError

_FORBIDDEN_TABLES = frozenset(
    {
        "pg_stat_statements",
        "pg_stat_activity",
        "pg_tables",
        "pg_views",
        "pg_indexes",
        "pg_proc",
        "pg_class",
        "pg_description",
        "pg_shdescription",
        "pg_database",
        "pg_stat_user_tables",
        "pg_stat_database",
        "pg_stat_all_tables",
        "pg_statio_all_tables",
    }
)

_FORBIDDEN_SCHEMAS = frozenset({"pg_catalog", "information_schema", "pg_toast"})

_FORBIDDEN_FUNCTIONS = frozenset(
    {
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_logfile_name",
        "current_query",
        "pg_backend_pid",
        "pg_stat_get_activity",
        "pg_stat_get_backend_activity",
    }
)


class SQLSecurityGuard:
    """Validatore per l'integrità e l'isolamento dell'esecuzione SQL nella sandbox."""

    def verify_expression(self, expression: exp.Expression, allowed_schema: str = "") -> None:
        """Ispeziona l'AST per rilevare violazioni di sicurezza o tentativi di cheating."""
        for table in expression.find_all(exp.Table):
            tbl_name = (table.name or "").lower()
            schema_name = (table.db or "").lower()

            if tbl_name in _FORBIDDEN_TABLES or schema_name in _FORBIDDEN_SCHEMAS:
                msg = f"Accesso non consentito a catalogo o cronologia query: '{table.sql()}'."
                raise SandboxSolverError(msg)

            if schema_name and allowed_schema and schema_name != allowed_schema.lower():
                msg = f"Accesso non consentito a schemi esterni: '{schema_name}'."
                raise SandboxSolverError(msg)

        for func in expression.find_all(exp.Anonymous, exp.Func):
            func_name = (func.name or "").lower()
            if func_name in _FORBIDDEN_FUNCTIONS:
                msg = f"Chiamata a funzione di sistema non consentita: '{func_name}'."
                raise SandboxSolverError(msg)
