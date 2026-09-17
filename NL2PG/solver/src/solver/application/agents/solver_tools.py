"""Modulo per la definizione dei 5 strumenti del solver tramite LangChain e LangGraph.

:author: Riccardo Morabito
"""

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from psycopg.errors import Error as PgError
from sqlglot import parse_one
from sqlglot.errors import ParseError, TokenError

from solver.domain.exceptions import SandboxSolverError

from solver.domain.models.state import SolverTaskStateDTO
from solver.domain.ports.outbound.datalog_port import DatalogPort
from solver.domain.ports.outbound.rag_port import DocRAGPort
from solver.domain.ports.outbound.sandbox_port import SandboxPort
from solver.domain.services.datalog_utils import DatalogUtils


class SolverToolFactory:
    """Factory per la creazione e parametrizzazione dei 5 strumenti del solver."""

    def __init__(
        self,
        rag: DocRAGPort,
        sandbox: SandboxPort,
        datalog: DatalogPort,
        state: SolverTaskStateDTO,
    ) -> None:
        """Inietta le porte di infrastruttura e lo stato del task corrente."""
        self._rag = rag
        self._sandbox = sandbox
        self._datalog = datalog
        self._state = state

    def search_knowledge(self, query: str) -> str:
        """Interroga il database vettoriale RAG (3.043+ chunk) per ottenere evidenza."""
        return self._rag.search_documentation(query)

    def validate_sql(self, code: str) -> str:
        """Valida la correttezza sintattica AST del codice SQL/DDL tramite parser sqlglot."""
        try:
            parse_one(code, read="postgres")
            return "Sintassi SQL valida."
        except (ParseError, TokenError, ValueError, AttributeError) as e:
            return f"Errore sintattico SQL: {e}"

    def validate_datalog(self, code: str) -> str:
        """Valida la sintassi formale delle regole Datalog tramite Clingo."""
        is_valid, msg = self._datalog.validate_syntax(code)
        return msg if is_valid else f"Errore sintattico Datalog: {msg}"

    def dry_run_sql(self, code: str) -> str:
        """Esegue fisicamente il codice DDL o la query SELECT nella Sandbox PostgreSQL."""
        try:
            if any(
                k in code.upper()
                for k in ("CREATE TABLE", "ALTER TABLE", "CREATE DOMAIN", "CREATE TYPE")
            ):
                self._sandbox.execute_ddl(self._state.sandbox_schema, code)
                return "DDL eseguito con successo nel sandbox PostgreSQL."
            cols, rows = self._sandbox.run_query(self._state.sandbox_schema, code)
            return (
                f"Query eseguita. Colonne: {cols}. Conteggio righe: {len(rows)}. Righe: {rows[:3]}"
            )
        except (SandboxSolverError, PgError, ValueError, TypeError) as e:
            return f"Errore esecuzione PostgreSQL Sandbox: {e}"

    def dry_run_datalog(self, rules: str) -> str:
        """Esegue le regole Datalog sul solver simbolico Clingo con i fatti di test."""
        active_ddl = self._state.gold_schema_ddl or self._state.generated_schema_ddl or ""
        schemas = DatalogUtils.extract_schema_from_ddl(active_ddl)
        facts, scale, _ = DatalogUtils.build_datalog_facts(
            self._state.gold_data_inserts, schemas=schemas
        )
        self._state.datalog_scale = scale
        success, rows, err = self._datalog.run_datalog(facts, rules, predicate_name="query")
        if success:
            return f"Datalog eseguito su Clingo. Righe ottenute ({len(rows)}): {rows[:5]}"
        return f"Errore esecuzione Clingo: {err}"

    def build_tools(
        self,
    ) -> tuple[list[BaseTool], list[dict[str, Any]], dict[str, BaseTool]]:
        """Costruisce i 5 strumenti StructuredTool di LangChain privi di funzioni annidate."""
        t1 = StructuredTool.from_function(
            func=self.search_knowledge,
            name="search_knowledge_and_evidence",
            description=(
                "Interroga il database vettoriale RAG (3.043+ chunk) per ottenere: "
                "1. RISOLUZIONE DI GERGO E SINONIMI (Twist); "
                "2. EVIDENZA E FORMULE AZIENDALI (BIRD-SQL); "
                "3. SCHEMI E PATTERN RELAZIONALI (Spider); "
                "4. MANUALE POSTGRESQL 17; "
                "5. SINTASSI DATALOG & CLINGO."
            ),
        )
        t2 = StructuredTool.from_function(
            func=self.validate_sql,
            name="validate_sql_syntax",
            description=(
                "Valida la correttezza sintattica AST del codice SQL/DDL tramite parser sqlglot."
            ),
        )
        t3 = StructuredTool.from_function(
            func=self.validate_datalog,
            name="validate_datalog_syntax",
            description="Valida la sintassi formale delle regole Datalog tramite Clingo.",
        )
        t4 = StructuredTool.from_function(
            func=self.dry_run_sql,
            name="dry_run_sql",
            description=(
                "Esegue fisicamente il codice DDL o la query SELECT nella Sandbox PostgreSQL "
                "restituendo il numero di righe e i primi record o eventuali errori."
            ),
        )
        t5 = StructuredTool.from_function(
            func=self.dry_run_datalog,
            name="dry_run_datalog",
            description=(
                "Esegue le regole Datalog sul solver simbolico Clingo con i fatti di test "
                "per ispezionare i risultati del predicato target `query(...)`."
            ),
        )

        tools: list[BaseTool] = [t1, t2, t3, t4, t5]
        tools_by_name = {t.name: t for t in tools}
        tools_by_name["search_documentation"] = t1
        openai_schemas = [convert_to_openai_tool(t) for t in tools]

        return tools, openai_schemas, tools_by_name
