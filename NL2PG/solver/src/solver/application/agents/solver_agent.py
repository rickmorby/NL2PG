"""Agente di risoluzione autonomo basato sul paradigma Recursive ReAct ad albero.

Implementa la scomposizione per sotto-problemi (divide-et-impera), l'esecuzione
dei sotto-nodi in contesti isolati, la retroazione con strumenti dedicati (RAG,
validazione sintattica, dry-run PostgreSQL e Clingo), tentativi di sottomissione
vincolanti (fino a 5) e backtracking guidato dal nodo genitore, come formalizzato
nel Capitolo 4 della tesi.

:author: Riccardo Morabito
"""

from logging import getLogger
from re import DOTALL, IGNORECASE, compile as re_compile, findall as re_findall
from typing import Any

from psycopg.errors import Error as PgError
from sqlglot import parse_one
from sqlglot.errors import ParseError, TokenError

from solver.application.agents.solver_tools import SolverToolFactory
from solver.domain.exceptions import SolverException
from solver.domain.models.solver import RecipeResultDTO, RecipeType, SchemaSource
from solver.domain.models.state import SolverTaskStateDTO
from solver.domain.models.trace import ToolCallDTO, ToolTraceDTO
from solver.domain.ports.outbound.datalog_port import DatalogPort
from solver.domain.ports.outbound.llm_port import LLMGeneratorPort
from solver.domain.ports.outbound.prompt_port import PromptPort
from solver.domain.ports.outbound.rag_port import DocRAGPort
from solver.domain.ports.outbound.sandbox_port import SandboxPort
from solver.domain.services.datalog_utils import DatalogUtils
from solver.domain.services.sql_repair import PostgresSQLRepair

_log = getLogger("solver.agents.solver_agent")

_RE_MARKDOWN_BLOCK = re_compile(
    r"```(?:sql|datalog|postgres|prolog|asp|clingo)?\s*(.*?)\s*```", flags=DOTALL | IGNORECASE
)
_RE_MARKDOWN_PREFIX = re_compile(r"^```[a-zA-Z]*\n?")
_RE_MARKDOWN_SUFFIX = re_compile(r"\n?```$")
_RE_PROLOG_HEADER = re_compile(r"^prolog\s*\n?", flags=IGNORECASE)
_MIN_NAME_LEN = 2
_RE_ENTITY_HINTS = re_compile(
    r"\b(?:tabella|entit[aà]|relazione)\s+([a-zA-Z_][a-zA-Z0-9_]*)", flags=IGNORECASE
)

MAX_SUBMISSION_ATTEMPTS = 5
MAX_RECURSIVE_TOOL_ITERATIONS = 20


class _ToolExecutorHandler:
    """Esecutore di chiamate a strumenti per l'agente solver."""

    def __init__(self, tools_by_name: dict[str, Any]) -> None:
        """Inizializza l'handler con la mappa dei tool disponibili."""
        self._tools_by_name = tools_by_name

    def __call__(self, tool_name: str, args: dict[str, Any]) -> tuple[str, bool]:
        """Esegue il tool target catturando eventuali errori."""
        target_tool = self._tools_by_name.get(tool_name)
        if not target_tool:
            return f"Strumento '{tool_name}' non riconosciuto.", False
        try:
            res = target_tool.invoke(args)
            is_err = "Errore" in str(res) or "error" in str(res).lower()
            return str(res), not is_err
        except (
            SolverException,
            PgError,
            ParseError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            return f"Errore esecuzione strumento: {e}", False


class SolverAgent:
    """Agente di risoluzione per Text-to-Schema e Text-to-Query (Recursive ReAct)."""

    @staticmethod
    def clean_code_output(text: str) -> str:
        """Rimuove markdown fences, prefissi prolog ed estrae il codice pulito."""
        cleaned = text.strip()
        if "```" in cleaned:
            m = _RE_MARKDOWN_BLOCK.search(cleaned)
            if m:
                cleaned = m.group(1).strip()
            else:
                cleaned = _RE_MARKDOWN_PREFIX.sub("", cleaned)
                cleaned = _RE_MARKDOWN_SUFFIX.sub("", cleaned).strip()

        return _RE_PROLOG_HEADER.sub("", cleaned).strip()

    def __init__(
        self,
        llm: LLMGeneratorPort,
        sandbox: SandboxPort,
        datalog: DatalogPort,
        rag: DocRAGPort,
        prompts: PromptPort | None = None,
    ) -> None:
        """Inietta le porte di infrastruttura e i servizi ausiliari."""
        self._llm = llm
        self._sandbox = sandbox
        self._datalog = datalog
        self._rag = rag
        self._prompts = prompts
        self._repair = PostgresSQLRepair()

    def solve_recipe(  # noqa: PLR0911
        self,
        recipe: str,
        state: SolverTaskStateDTO,
        schema_source: str = SchemaSource.GOLD.value,
        chain_role: str = "default",
        max_iterations: int = MAX_RECURSIVE_TOOL_ITERATIONS,
        sql_to_translate: str | None = None,
    ) -> RecipeResultDTO:
        """Esegue la risoluzione del compito adottando Flat ReAct o Recursive ReAct."""
        if recipe == RecipeType.TEXT_TO_SQL_ZERO_SHOT.value:
            return self._solve_zero_shot(recipe, state, schema_source, chain_role)

        if recipe == RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value:
            if state.n_tables > 1 or state.difficulty_label == "hard":
                return self._solve_schema_recursive(state, chain_role, max_iterations)
            return self._solve_flat_react(recipe, state, schema_source, chain_role, max_iterations)

        if recipe == RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value:
            if state.difficulty_label == "hard":
                return self._solve_sql_recursive(state, schema_source, chain_role, max_iterations)
            return self._solve_flat_react(recipe, state, schema_source, chain_role, max_iterations)

        if recipe == RecipeType.TEXT_TO_DATALOG_RAG_CLINGO.value:
            if state.difficulty_label == "hard":
                return self._solve_datalog_recursive(
                    state, schema_source, chain_role, max_iterations
                )
            return self._solve_flat_react(recipe, state, schema_source, chain_role, max_iterations)

        if recipe == RecipeType.SQL_TO_DATALOG_TRANSPILED.value:
            return self._solve_transpile_recursive(
                state, schema_source, chain_role, max_iterations, sql_to_translate
            )

        return self._solve_flat_react(recipe, state, schema_source, chain_role, max_iterations)

    def _solve_zero_shot(
        self, recipe: str, state: SolverTaskStateDTO, schema_source: str, chain_role: str
    ) -> RecipeResultDTO:
        """Esegue la linea di base Zero-Shot senza strumenti."""
        sys_p, user_p = self._build_prompts(recipe, state, schema_source)
        raw_out, _trace_data, _ = self._llm.call_with_tools(
            model_role=chain_role,
            system_prompt=sys_p,
            user_prompt=user_p,
            tools=[],
            tool_executor=lambda _n, _a: ("", False),
            max_iterations=1,
        )
        cleaned = self._repair.repair(self.clean_code_output(raw_out))
        return RecipeResultDTO(
            recipe=recipe,
            schema_source=schema_source,
            generated_code=cleaned,
            trace=ToolTraceDTO(calls=[], is_one_shot=True),
        )

    def _solve_flat_react(
        self,
        recipe: str,
        state: SolverTaskStateDTO,
        schema_source: str,
        chain_role: str,
        max_iterations: int,
        sql_to_translate: str | None = None,
    ) -> RecipeResultDTO:
        """Esegue il ciclo ReAct con validazione sintattica vincolante (max 5 tentativi)."""
        sys_p, user_p = self._build_prompts(recipe, state, schema_source, sql_to_translate)
        factory = SolverToolFactory(self._rag, self._sandbox, self._datalog, state)
        _tools, openai_tools, tools_by_name = factory.build_tools()
        executor = _ToolExecutorHandler(tools_by_name)

        all_calls: list[ToolCallDTO] = []
        code_result = ""

        for attempt in range(1, MAX_SUBMISSION_ATTEMPTS + 1):
            iter_budget = max(max_iterations - len(all_calls), 2)
            raw_out, trace_data, _ = self._llm.call_with_tools(
                model_role=chain_role,
                system_prompt=sys_p,
                user_prompt=user_p,
                tools=openai_tools,
                tool_executor=executor,
                max_iterations=iter_budget,
            )

            for t in trace_data:
                all_calls.append(
                    ToolCallDTO(
                        tool_name=t["tool_name"],
                        arguments=t["arguments"],
                        output_summary=t["output_summary"],
                        step=len(all_calls) + 1,
                        success=t["success"],
                    )
                )

            cleaned = self.clean_code_output(raw_out)
            if "sql" in recipe.lower() or "schema" in recipe.lower():
                cleaned = self._repair.repair(cleaned)

            is_valid, err_msg = self._validate_code_syntax(recipe, cleaned)
            if is_valid or attempt == MAX_SUBMISSION_ATTEMPTS:
                code_result = cleaned
                break

            user_p += (
                f"\n\n[TENTATIVO {attempt} RESPINTA PER ANOMALIA SINTATTICA]:\n{err_msg}\n"
                "Correggi tassativamente il codice fornendo solo la formulazione corretta."
            )

        return RecipeResultDTO(
            recipe=recipe,
            schema_source=schema_source,
            generated_code=code_result,
            trace=ToolTraceDTO(calls=all_calls, is_one_shot=(len(all_calls) == 0)),
        )

    def _solve_schema_recursive(
        self, state: SolverTaskStateDTO, chain_role: str, max_iterations: int
    ) -> RecipeResultDTO:
        """Scomposizione per entita' (Stage 2): CREATE TABLE figlie + ALTER TABLE genitore."""
        all_calls: list[ToolCallDTO] = []
        entities = self._extract_entity_names(state.story)
        table_definitions: list[str] = []

        for entity in entities:
            sub_sys = (
                "Sei un Database Architect PostgreSQL 17. Genera esclusivamente l'istruzione "
                f"CREATE TABLE per la singola entita' '{entity}' comprensiva di sole colonne "
                "fisiche e chiave primaria (PRIMARY KEY), omettendo vincoli di chiave esterna."
            )
            sub_user = f"CONTESTO AZIENDALE:\n{state.story}\n\nENTITA' TARGET:\n{entity}"
            factory = SolverToolFactory(self._rag, self._sandbox, self._datalog, state)
            _, openai_tools, tools_by_name = factory.build_tools()
            executor = _ToolExecutorHandler(tools_by_name)

            raw_t, trace_t, _ = self._llm.call_with_tools(
                model_role=chain_role,
                system_prompt=sub_sys,
                user_prompt=sub_user,
                tools=openai_tools,
                tool_executor=executor,
                max_iterations=min(6, max_iterations),
            )
            for t in trace_t:
                all_calls.append(
                    ToolCallDTO(
                        tool_name=t["tool_name"],
                        arguments=t["arguments"],
                        output_summary=t["output_summary"],
                        step=len(all_calls) + 1,
                        success=t["success"],
                    )
                )
            cleaned_t = self._repair.repair(self.clean_code_output(raw_t))
            if "CREATE TABLE" in cleaned_t.upper():
                table_definitions.append(cleaned_t)

        if not table_definitions:
            return self._solve_flat_react(
                RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value,
                state,
                SchemaSource.GOLD.value,
                chain_role,
                max_iterations,
            )

        base_ddl = "\n\n".join(table_definitions)
        parent_sys = (
            "Sei un Database Architect PostgreSQL 17. Ricevi le definizioni di base CREATE TABLE "
            "e devi completare lo schema aggiungendo eventuali vincoli di integrita' referenziale "
            "tramite clausole differite 'ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY'. "
            "Restituisci l'intero DDL valido assemblato."
        )
        parent_user = (
            f"STORIA AZIENDALE:\n{state.story}\n\n"
            f"TABELLE BASE CREATE:\n{base_ddl}\n\n"
            "Assembla il DDL completo inserendo i vincoli referenziali necessari."
        )
        factory = SolverToolFactory(self._rag, self._sandbox, self._datalog, state)
        _, openai_tools, tools_by_name = factory.build_tools()
        executor = _ToolExecutorHandler(tools_by_name)

        final_ddl = base_ddl
        for _attempt in range(1, MAX_SUBMISSION_ATTEMPTS + 1):
            raw_p, trace_p, _ = self._llm.call_with_tools(
                model_role=chain_role,
                system_prompt=parent_sys,
                user_prompt=parent_user,
                tools=openai_tools,
                tool_executor=executor,
                max_iterations=min(8, max_iterations),
            )
            for t in trace_p:
                all_calls.append(
                    ToolCallDTO(
                        tool_name=t["tool_name"],
                        arguments=t["arguments"],
                        output_summary=t["output_summary"],
                        step=len(all_calls) + 1,
                        success=t["success"],
                    )
                )
            assembled = self._repair.repair(self.clean_code_output(raw_p))
            if "CREATE TABLE" in assembled.upper():
                final_ddl = assembled
                break

        return RecipeResultDTO(
            recipe=RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value,
            schema_source=SchemaSource.GOLD.value,
            generated_code=final_ddl,
            trace=ToolTraceDTO(calls=all_calls, is_one_shot=False),
        )

    def _solve_sql_recursive(
        self, state: SolverTaskStateDTO, schema_source: str, chain_role: str, max_iterations: int
    ) -> RecipeResultDTO:
        """Scomposizione ricorsiva Text-to-SQL per compiti complessi (divide-et-impera)."""
        all_calls: list[ToolCallDTO] = []
        raw_ddl = (
            state.gold_schema_ddl
            if schema_source == SchemaSource.GOLD.value
            else (state.generated_schema_ddl or "")
        )

        plan_sys = (
            "Sei un Query Architect PostgreSQL 17. Scomponi la richiesta in sotto-query "
            "o Common Table Expressions (CTE) necessarie per isolare filtri e aggregazioni "
            "complesse."
        )
        plan_user = (
            f"SCHEMA DDL:\n{raw_ddl}\n\n"
            f"DOMANDA UTENTE:\n{state.question}\n\n"
            f"STORIA:\n{state.story}\n\n"
            "Proponi le CTE o sotto-espressioni chiave per rispondere alla domanda."
        )
        factory = SolverToolFactory(self._rag, self._sandbox, self._datalog, state)
        _, openai_tools, tools_by_name = factory.build_tools()
        executor = _ToolExecutorHandler(tools_by_name)

        raw_sub, trace_sub, _ = self._llm.call_with_tools(
            model_role=chain_role,
            system_prompt=plan_sys,
            user_prompt=plan_user,
            tools=openai_tools,
            tool_executor=executor,
            max_iterations=min(6, max_iterations),
        )
        for t in trace_sub:
            all_calls.append(
                ToolCallDTO(
                    tool_name=t["tool_name"],
                    arguments=t["arguments"],
                    output_summary=t["output_summary"],
                    step=len(all_calls) + 1,
                    success=t["success"],
                )
            )

        parent_sys = (
            self._prompts.load("sql_rag")
            if self._prompts
            else "Sei un Data Engineer PostgreSQL 17."
        )
        parent_user = (
            f"SCHEMA DDL:\n{raw_ddl}\n\n"
            f"DOMANDA UTENTE:\n{state.question}\n\n"
            f"STORIA:\n{state.story}\n\n"
            f"STRUTTURA SCOMPOSIZIONE CTE PROPOSTA:\n{raw_sub}\n\n"
            "Formula ed esegui nella Sandbox la query PostgreSQL finale definitiva."
        )

        final_query = ""
        for attempt in range(1, MAX_SUBMISSION_ATTEMPTS + 1):
            raw_p, trace_p, _ = self._llm.call_with_tools(
                model_role=chain_role,
                system_prompt=parent_sys,
                user_prompt=parent_user,
                tools=openai_tools,
                tool_executor=executor,
                max_iterations=min(12, max_iterations),
            )
            for t in trace_p:
                all_calls.append(
                    ToolCallDTO(
                        tool_name=t["tool_name"],
                        arguments=t["arguments"],
                        output_summary=t["output_summary"],
                        step=len(all_calls) + 1,
                        success=t["success"],
                    )
                )
            cleaned_q = self._repair.repair(self.clean_code_output(raw_p))
            is_valid, err_msg = self._validate_code_syntax(
                RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value, cleaned_q
            )
            if is_valid or attempt == MAX_SUBMISSION_ATTEMPTS:
                final_query = cleaned_q
                break
            parent_user += f"\n[ERRORE TENTATIVO {attempt}]: {err_msg}. Correggi la sintassi SQL."

        return RecipeResultDTO(
            recipe=RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value,
            schema_source=schema_source,
            generated_code=final_query,
            trace=ToolTraceDTO(calls=all_calls, is_one_shot=False),
        )

    def _solve_datalog_recursive(
        self, state: SolverTaskStateDTO, schema_source: str, chain_role: str, max_iterations: int
    ) -> RecipeResultDTO:
        """Scomposizione ricorsiva Text-to-Datalog con verifica di sicurezza variabili Clingo."""
        all_calls: list[ToolCallDTO] = []
        raw_ddl = (
            state.gold_schema_ddl
            if schema_source == SchemaSource.GOLD.value
            else (state.generated_schema_ddl or "")
        )

        sys_p = (
            self._prompts.load("datalog_rag")
            if self._prompts
            else "Sei un Logic Specialist Clingo ASP."
        )
        user_p = (
            f"SCHEMA DDL:\n{raw_ddl}\n\n"
            f"SCALA NUMERICA DEI FATTI: x{state.datalog_scale or 1000}\n\n"
            f"STORIA AZIENDALE:\n{state.story}\n\n"
            f"DOMANDA UTENTE:\n{state.question}"
        )

        factory = SolverToolFactory(self._rag, self._sandbox, self._datalog, state)
        _, openai_tools, tools_by_name = factory.build_tools()
        executor = _ToolExecutorHandler(tools_by_name)

        final_rules = ""
        for attempt in range(1, MAX_SUBMISSION_ATTEMPTS + 1):
            raw_dl, trace_dl, _ = self._llm.call_with_tools(
                model_role=chain_role,
                system_prompt=sys_p,
                user_prompt=user_p,
                tools=openai_tools,
                tool_executor=executor,
                max_iterations=min(14, max_iterations),
            )
            for t in trace_dl:
                all_calls.append(
                    ToolCallDTO(
                        tool_name=t["tool_name"],
                        arguments=t["arguments"],
                        output_summary=t["output_summary"],
                        step=len(all_calls) + 1,
                        success=t["success"],
                    )
                )
            cleaned_dl = self.clean_code_output(raw_dl)
            is_valid, err_msg = self._validate_code_syntax(
                RecipeType.TEXT_TO_DATALOG_RAG_CLINGO.value, cleaned_dl
            )
            if is_valid or attempt == MAX_SUBMISSION_ATTEMPTS:
                final_rules = cleaned_dl
                break
            user_p += (
                f"\n[ERRORE CLINGO TENTATIVO {attempt}]: {err_msg}.\n"
                "Vincola ogni variabile non sicura (UNBOUND_VAR) a predicati positivi di dominio."
            )

        return RecipeResultDTO(
            recipe=RecipeType.TEXT_TO_DATALOG_RAG_CLINGO.value,
            schema_source=schema_source,
            generated_code=final_rules,
            trace=ToolTraceDTO(calls=all_calls, is_one_shot=False),
        )

    def _solve_transpile_recursive(
        self,
        state: SolverTaskStateDTO,
        schema_source: str,
        chain_role: str,
        max_iterations: int,
        sql_to_translate: str | None,
    ) -> RecipeResultDTO:
        """Traduzione SQL-to-Datalog governata da Recursive ReAct su clausole dichiarative."""
        all_calls: list[ToolCallDTO] = []
        raw_ddl = (
            state.gold_schema_ddl
            if schema_source == SchemaSource.GOLD.value
            else (state.generated_schema_ddl or "")
        )

        sys_p = (
            self._prompts.load("sql_transpiled")
            if self._prompts
            else "Sei uno specialista Clingo ASP."
        )
        user_p = (
            f"SCHEMA RELAZIONALE:\n{raw_ddl}\n\n"
            f"SCALA NUMERICA DEI FATTI: x{state.datalog_scale or 1000}\n\n"
            f"QUERY SQL DA TRADURRE:\n{sql_to_translate or state.gold_query}\n\n"
            f"STORIA AZIENDALE:\n{state.story}\n\n"
            f"DOMANDA UTENTE:\n{state.question}"
        )

        factory = SolverToolFactory(self._rag, self._sandbox, self._datalog, state)
        _, openai_tools, tools_by_name = factory.build_tools()
        executor = _ToolExecutorHandler(tools_by_name)

        final_rules = ""
        for attempt in range(1, MAX_SUBMISSION_ATTEMPTS + 1):
            raw_tr, trace_tr, _ = self._llm.call_with_tools(
                model_role=chain_role,
                system_prompt=sys_p,
                user_prompt=user_p,
                tools=openai_tools,
                tool_executor=executor,
                max_iterations=min(12, max_iterations),
            )
            for t in trace_tr:
                all_calls.append(
                    ToolCallDTO(
                        tool_name=t["tool_name"],
                        arguments=t["arguments"],
                        output_summary=t["output_summary"],
                        step=len(all_calls) + 1,
                        success=t["success"],
                    )
                )
            cleaned_tr = self.clean_code_output(raw_tr)
            is_valid, err_msg = self._validate_code_syntax(
                RecipeType.SQL_TO_DATALOG_TRANSPILED.value, cleaned_tr
            )
            if is_valid or attempt == MAX_SUBMISSION_ATTEMPTS:
                final_rules = cleaned_tr
                break
            user_p += (
                f"\n[ERRORE TRADUZIONE CLINGO {attempt}]: {err_msg}. "
                "Correggi le variabili non sicure."
            )

        return RecipeResultDTO(
            recipe=RecipeType.SQL_TO_DATALOG_TRANSPILED.value,
            schema_source=schema_source,
            generated_code=final_rules,
            trace=ToolTraceDTO(calls=all_calls, is_one_shot=False),
        )

    def _validate_code_syntax(self, recipe: str, code: str) -> tuple[bool, str]:
        """Esegue la validazione sintattica vincolante conformemente alla Sezione 4.2."""
        if not code or not code.strip():
            return False, "Codice generato vuoto."

        if "sql" in recipe.lower() or "schema" in recipe.lower():
            try:
                parse_one(code, read="postgres")
                return True, "Sintassi SQL valida."
            except (ParseError, TokenError, ValueError, AttributeError) as e:
                return False, f"Errore sintassi SQL: {e}"

        is_ok, msg = self._datalog.validate_syntax(code)
        return is_ok, msg

    def _extract_entity_names(self, story: str) -> list[str]:
        """Estrae i nomi probabili delle entita' dalla prosa aziendale per la scomposizione."""
        matches = _RE_ENTITY_HINTS.findall(story)
        names = [m.lower() for m in matches if len(m) > _MIN_NAME_LEN]
        if not names:
            tokens = re_findall(r"\b[a-zA-Z_]{3,20}\b", story.lower())
            freq: dict[str, int] = {}
            stopwords = {
                "della",
                "delle",
                "degli",
                "questa",
                "questo",
                "azienda",
                "sistema",
                "gestione",
            }
            for tok in tokens:
                if tok not in stopwords:
                    freq[tok] = freq.get(tok, 0) + 1
            sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            names = [t[0] for t in sorted_tokens[:3]]
        return list(dict.fromkeys(names))[:4]

    def _build_prompts(
        self,
        recipe: str,
        state: SolverTaskStateDTO,
        schema_source: str,
        sql_to_translate: str | None = None,
    ) -> tuple[str, str]:
        """Costruisce il system prompt ed il user prompt per la ricetta sperimentale."""
        raw_ddl = (
            state.gold_schema_ddl
            if schema_source == SchemaSource.GOLD.value or not state.generated_schema_ddl
            else state.generated_schema_ddl
        )
        effective_ddl = (
            DatalogUtils.enrich_ddl_with_samples(raw_ddl, state.gold_data_inserts)
            if schema_source == SchemaSource.GOLD.value and state.gold_data_inserts
            else raw_ddl
        )

        if recipe == RecipeType.TEXT_TO_SCHEMA_RAG_SANDBOX.value:
            sys_p = (
                self._prompts.load("schema")
                if self._prompts
                else "Sei un Database Architect PostgreSQL 17."
            )
            user_p = f"STORIA AZIENDALE:\n{state.story}"
            return sys_p, user_p

        if recipe == RecipeType.TEXT_TO_SQL_RAG_SANDBOX.value:
            sys_p = (
                self._prompts.load("sql_rag")
                if self._prompts
                else "Sei un Data Engineer PostgreSQL 17."
            )
            user_p = (
                f"SCHEMA DDL:\n{effective_ddl}\n\n"
                f"STORIA AZIENDALE:\n{state.story}\n\n"
                f"DOMANDA UTENTE:\n{state.question}"
            )
            return sys_p, user_p

        if recipe == RecipeType.TEXT_TO_SQL_ZERO_SHOT.value:
            sys_p = (
                self._prompts.load("sql_zero_shot")
                if self._prompts
                else "Sei un Data Engineer PostgreSQL 17."
            )
            user_p = (
                f"SCHEMA DDL:\n{effective_ddl}\n\n"
                f"STORIA AZIENDALE:\n{state.story}\n\n"
                f"DOMANDA UTENTE:\n{state.question}"
            )
            return sys_p, user_p

        if recipe == RecipeType.SQL_TO_DATALOG_TRANSPILED.value:
            sys_p = (
                self._prompts.load("sql_transpiled")
                if self._prompts
                else "Sei uno specialista di traduzione SQL verso Datalog Clingo."
            )
            user_p = (
                f"SCHEMA RELAZIONALE (colonne in ordine di dichiarazione):\n{effective_ddl}\n\n"
                f"SCALA NUMERICA DEI FATTI: x{state.datalog_scale or 1000}\n\n"
                f"QUERY SQL DA TRADURRE:\n{sql_to_translate or state.gold_query}\n\n"
                f"STORIA AZIENDALE (contesto di dominio):\n{state.story}\n\n"
                f"DOMANDA UTENTE:\n{state.question}"
            )
            return sys_p, user_p

        if recipe == RecipeType.TEXT_TO_DATALOG_RAG_CLINGO.value:
            sys_p = (
                self._prompts.load("datalog_rag")
                if self._prompts
                else "Sei un Principal Logic Programming Specialist (Clingo ASP)."
            )
            user_p = (
                f"SCHEMA RELAZIONALE (colonne in ordine di dichiarazione):\n{effective_ddl}\n\n"
                f"SCALA NUMERICA DEI FATTI: x{state.datalog_scale or 1000}\n\n"
                f"STORIA AZIENDALE:\n{state.story}\n\n"
                f"DOMANDA UTENTE:\n{state.question}"
            )
            return sys_p, user_p

        return "Sei un assistente per database relazionali.", f"Q: {state.question}"
