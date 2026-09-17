"""Utilità di dominio per la conversione da SQL INSERT a fatti Datalog Clingo-compatibili.

:author: Riccardo Morabito
"""

from collections import defaultdict
from typing import Any

from clingo import Symbol, SymbolType
from sqlglot import exp, parse as sqlglot_parse
from sqlglot.errors import ParseError, TokenError

from decimal import Decimal

from solver.domain.services.datalog_numeric import (
    DEFAULT_SCALE,
    MIN_PRECISE_SCALE,
    choose_scale,
    scale_sql_number,
)

_MIN_SAMPLE_LEN = 1
_MAX_SAMPLE_LEN = 30
_MIN_DISTINCT_COUNT = 1
_MAX_DISTINCT_COUNT = 6
_MAX_PREVIEW_VALUES = 4


class DatalogUtils:
    """Classe di utilità statica per le conversioni relazionali SQL-to-Datalog e campionamento."""

    @staticmethod
    def extract_schema_from_ddl(ddl_sql: str) -> dict[str, list[str]]:
        """Estrae l'elenco ordinato delle colonne per ciascuna tabella dal DDL."""
        if not ddl_sql or not ddl_sql.strip():
            return {}
        try:
            statements = sqlglot_parse(ddl_sql, read="postgres")
        except (ParseError, TokenError, ValueError, AttributeError):
            return {}
        schemas: dict[str, list[str]] = {}
        for statement in statements:
            if not isinstance(statement, exp.Create):
                continue
            table = statement.this.find(exp.Table)
            if table is None:
                continue
            columns = [column.name.lower() for column in statement.this.find_all(exp.ColumnDef)]
            if columns:
                schemas[table.name.lower()] = columns
        return schemas

    @staticmethod
    def enrich_ddl_with_samples(ddl_sql: str, inserts_sql: str) -> str:
        """Arricchisce il DDL con valori categorici reali di esempio (Standard BIRD-SQL)."""
        if not inserts_sql or not inserts_sql.strip():
            return ddl_sql

        try:
            parsed_inserts = sqlglot_parse(inserts_sql, read="postgres")
        except (ParseError, TokenError, ValueError, AttributeError):
            return ddl_sql

        table_samples = DatalogUtils._extract_table_samples(parsed_inserts)
        return DatalogUtils._annotate_ddl_lines(ddl_sql, table_samples)

    @staticmethod
    def _extract_table_samples(
        parsed_inserts: list[exp.Expression],
    ) -> dict[str, dict[str, set[str]]]:
        """Estrae i valori categorici distinti dalle istruzioni INSERT."""
        table_samples: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for stmt in parsed_inserts:
            if isinstance(stmt, exp.Insert):
                DatalogUtils._collect_insert_samples(stmt, table_samples)
        return table_samples

    @staticmethod
    def _collect_insert_samples(
        stmt: exp.Insert, table_samples: dict[str, dict[str, set[str]]]
    ) -> None:
        """Raccoglie i campioni di valori da una singola istruzione INSERT."""
        tbl = stmt.find(exp.Table)
        if not tbl or not isinstance(stmt.expression, exp.Values):
            return
        tbl_name = tbl.name.lower()
        explicit_cols = (
            [c.name.lower() for c in stmt.this.expressions]
            if isinstance(stmt.this, exp.Schema)
            else []
        )

        for tup in stmt.expression.expressions:
            if isinstance(tup, exp.Tuple):
                for i, val in enumerate(tup.expressions):
                    if i < len(explicit_cols):
                        cname = explicit_cols[i]
                        raw = val.sql(dialect="postgres").strip("'\"")
                        if (
                            _MIN_SAMPLE_LEN < len(raw) < _MAX_SAMPLE_LEN
                            and raw.lower() not in ("null", "none", "true", "false")
                            and not raw.isdigit()
                        ):
                            table_samples[tbl_name][cname].add(raw)

    @staticmethod
    def _annotate_ddl_lines(ddl_sql: str, table_samples: dict[str, dict[str, set[str]]]) -> str:
        """Annota le righe dello schema DDL con i valori categorici identificati."""
        lines = ddl_sql.split("\n")
        annotated = []
        current_tbl = ""

        for line in lines:
            if "CREATE TABLE" in line.upper():
                parts = line.split()
                idx = parts.index("TABLE") if "TABLE" in parts else -1
                if idx != -1 and idx + 1 < len(parts):
                    current_tbl = parts[idx + 1].strip(' ("`').lower()

            col_match = None
            if current_tbl and current_tbl in table_samples:
                for cname, samples in table_samples[current_tbl].items():
                    if (
                        f" {cname} " in f" {line.lower()} "
                        and _MIN_DISTINCT_COUNT <= len(samples) <= _MAX_DISTINCT_COUNT
                    ):
                        col_match = sorted(samples)[:_MAX_PREVIEW_VALUES]
                        break

            if col_match:
                sample_str = ", ".join(f"'{s}'" for s in col_match)
                annotated.append(f"{line}  -- valori nel DB: [{sample_str}]")
            else:
                annotated.append(line)

        return "\n".join(annotated)

    @staticmethod
    def build_datalog_facts(
        inserts_sql: str, schemas: dict[str, list[str]] | None = None
    ) -> tuple[str, int, bool]:
        """Converte le INSERT in fatti Datalog: ``(fatti, scala, preciso)``.

        La scala e' scelta dai dati per mantenere l'aritmetica Clingo a 32 bit
        entro il limite di sicurezza. ``preciso`` e' False quando almeno un
        valore perde cifre alla scala scelta: in quel caso il chiamante deve
        deviare al fallback LLM perche' filtri e aggregati non sono affidabili.
        """
        if not inserts_sql or not inserts_sql.strip():
            return "", DEFAULT_SCALE, True

        try:
            parsed = sqlglot_parse(inserts_sql, read="postgres")
        except (ParseError, TokenError, ValueError, AttributeError):
            return "", DEFAULT_SCALE, True

        max_abs, row_count = DatalogUtils._numeric_profile(parsed)
        scale = choose_scale(max_abs, row_count)
        precise = DatalogUtils._is_precise(parsed, scale)

        active_schemas = (
            {k.lower(): [c.lower() for c in v] for k, v in schemas.items()} if schemas else {}
        )

        table_row_counters: dict[str, int] = {}
        facts: list[str] = []
        for stmt in parsed:
            if isinstance(stmt, exp.Insert):
                stmt_facts = DatalogUtils._process_insert_stmt(
                    stmt, active_schemas, table_row_counters, scale
                )
                facts.extend(stmt_facts)

        return "\n".join(facts), scale, precise

    @staticmethod
    def _is_precise(_parsed: list[exp.Expression], scale: int) -> bool:
        """Verifica che la scala conservi abbastanza cifre decimali.

        Alla scala 100 l'errore di arrotondamento massimo e' 0.005, assorbito
        dall'epsilon del comparatore; scale inferiori spostano i filtri.
        """
        return scale >= MIN_PRECISE_SCALE

    @staticmethod
    def _numeric_profile(parsed: list[exp.Expression]) -> tuple[Decimal, int]:
        """Valore assoluto massimo e numero di tuple totali nelle INSERT."""
        max_abs = Decimal(0)
        row_count = 0
        for stmt in parsed:
            if not isinstance(stmt, exp.Insert):
                continue
            for tup in stmt.find_all(exp.Tuple):
                row_count += 1
                for literal in tup.find_all(exp.Literal):
                    if literal.is_number:
                        max_abs = max(max_abs, abs(Decimal(str(literal.this))))
        return max_abs, row_count

    @staticmethod
    def _process_insert_stmt(
        stmt: exp.Insert,
        active_schemas: dict[str, list[str]],
        table_row_counters: dict[str, int],
        scale: int,
    ) -> list[str]:
        """Elabora una singola istruzione INSERT generando i fatti Datalog corrispondenti."""
        tbl = stmt.find(exp.Table)
        if not tbl or not isinstance(stmt.expression, exp.Values):
            return []

        tbl_name = tbl.name.lower()
        explicit_cols = (
            [c.name.lower() for c in stmt.this.expressions]
            if isinstance(stmt.this, exp.Schema)
            else []
        )
        ddl_cols = active_schemas.get(tbl_name, [])

        table_row_counters.setdefault(tbl_name, 0)
        stmt_facts = []
        for tup in stmt.expression.expressions:
            if isinstance(tup, exp.Tuple):
                table_row_counters[tbl_name] += 1
                row_id = table_row_counters[tbl_name]
                formatted_args = DatalogUtils._align_tuple_to_ddl(
                    tup.expressions, explicit_cols, ddl_cols, row_id, scale
                )
                args_str = ", ".join(formatted_args)
                stmt_facts.append(f"{tbl_name}({args_str}).")

        return stmt_facts

    @staticmethod
    def _align_tuple_to_ddl(
        tuple_exprs: list[exp.Expression],
        explicit_cols: list[str],
        ddl_cols: list[str],
        row_id: int,
        scale: int,
    ) -> list[str]:
        """Allinea posizionalmente i valori della tupla all'ordine delle colonne del DDL."""
        val_by_col: dict[str, str] = {}
        if explicit_cols and len(explicit_cols) == len(tuple_exprs):
            for col_name, expr in zip(explicit_cols, tuple_exprs, strict=False):
                val_by_col[col_name] = DatalogUtils._format_datalog_val(expr, scale)
        elif len(tuple_exprs) == len(ddl_cols):
            for col_name, expr in zip(ddl_cols, tuple_exprs, strict=False):
                val_by_col[col_name] = DatalogUtils._format_datalog_val(expr, scale)
        else:
            return [DatalogUtils._format_datalog_val(e, scale) for e in tuple_exprs]

        result = []
        for col_name in ddl_cols:
            if col_name in val_by_col:
                result.append(val_by_col[col_name])
            elif col_name in ("id", "pk", f"{col_name}_id", "codice"):
                result.append(str(row_id))
            else:
                result.append("null")

        return result

    @staticmethod
    def _format_datalog_val(expr: exp.Expression, scale: int = DEFAULT_SCALE) -> str:
        """Formatta una singola espressione SQL in un atomo o costante Datalog valida."""
        if isinstance(expr, exp.Literal):
            return DatalogUtils._format_literal_val(expr, scale)
        if isinstance(expr, exp.Null):
            return "null"
        if isinstance(expr, exp.Boolean):
            return "true" if expr.this else "false"

        sql_val = expr.sql(dialect="postgres").strip("'\"")
        return f'"{sql_val}"'

    @staticmethod
    def _format_literal_val(expr: exp.Literal, scale: int = DEFAULT_SCALE) -> str:
        """Formatta un literal stringa o numerico in Datalog."""
        if expr.is_string:
            escaped = expr.this.replace('"', '\\"')
            return f'"{escaped}"'
        if expr.is_number:
            try:
                return scale_sql_number(expr.this, scale)
            except ValueError:
                return expr.this
        return expr.this

    @staticmethod
    def extract_clingo_symbol_arg(arg: Symbol) -> Any:
        """Converte un Symbol di Clingo nel tipo primitivo Python nativo."""
        if arg.type == SymbolType.Number:
            return arg.number
        if arg.type == SymbolType.String:
            return arg.string
        if arg.type == SymbolType.Function:
            if arg.name == "null":
                return None
            if len(arg.arguments) == 0:
                return arg.name
        return str(arg)
