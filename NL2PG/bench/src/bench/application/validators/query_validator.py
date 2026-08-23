"""Modulo validatore applicativo per la validazione completa di una gold query SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from re import IGNORECASE, compile as re_compile
from typing import Any

from psycopg.errors import Error as PgError
from sqlglot import exp, find_tables, parse_one
from sqlglot.errors import ParseError

from bench.application.validators.mutation_tester import MutationTester
from bench.domain.exceptions import DatabaseClientError
from bench.domain.models.data import DataProfileDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.models.sql import GoldQueryDTO, GoldResultDTO
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.validation.error_feedback_builder import ErrorFeedbackBuilder
from bench.domain.services.validation.feature_checker import FeatureChecker
from bench.domain.services.validation.gold_normalizer import (
    canonicalize_rows,
    find_none_literal,
)

_MAX_DISTINCT_SAMPLES = 2
_RE_VOLATILE_TEXT = re_compile(
    r"\b(?:NOW\s*\(|LOCALTIME(?:STAMP)?\b|CLOCK_TIMESTAMP|TRANSACTION_TIMESTAMP|"
    r"STATEMENT_TIMESTAMP)",
    flags=IGNORECASE,
)


@dataclass
class QueryValidationResult:
    """Esito della validazione completa di una gold query."""

    is_valid: bool = True
    error: str = ""
    gold_result: GoldResultDTO | None = None


class QueryValidator:
    """Validatore applicativo per l'esecuzione e la validazione di una gold query SQL."""

    def __init__(
        self,
        sandbox: SandboxPort,
        feature_checker: FeatureChecker,
        mutation_tester: MutationTester,
    ):
        """Inizializza il validatore con la porta sandbox e i servizi di dominio."""
        self._sandbox = sandbox
        self._feature_checker = feature_checker
        self._mutation_tester = mutation_tester

    def validate(
        self,
        query: GoldQueryDTO,
        spec: SpecDTO,
        schema: str,
        profile: DataProfileDTO | None = None,
    ) -> QueryValidationResult:
        """Esegue la query, verifica feature e mutazioni, e restituisce il risultato gold."""
        ast_err, tree = self._validate_ast_rules(query, spec)
        if ast_err:
            return QueryValidationResult(is_valid=False, error=ast_err)

        if query.order_sensitive and tree:
            self._ensure_tiebreaker(query, tree, schema)

        return self._validate_execution(query, schema, tree, profile)

    def ensure_tiebreaker(self, query: GoldQueryDTO, schema: str) -> GoldQueryDTO:
        """API pubblica: garantisce l'ORDER BY univoco (usato alla promozione D1)."""
        try:
            tree = parse_one(query.query, read="postgres")
        except ParseError:
            return query
        self._ensure_tiebreaker(query, tree, schema)
        return query

    def _ensure_tiebreaker(self, query: GoldQueryDTO, tree: exp.Expression, schema: str) -> None:
        """Aggiunge automaticamente un tiebreaker univoco (GROUP BY o PK ASC) se non univoco."""
        order = tree.args.get("order")
        if not order or not order.expressions:
            return
        last_expr = order.expressions[-1]
        last = last_expr.this if isinstance(last_expr, exp.Ordered) else last_expr
        col = last.find(exp.Column) if last is not None else None
        try:
            model = self._sandbox.introspect_schema(schema)
        except Exception:  # noqa: BLE001
            return
        unique_cols = self._collect_unique_columns(model)
        target_col = self._resolve_column_alias(tree, col.name.lower()) if col else ""
        if target_col in unique_cols:
            return

        group = tree.args.get("group")
        if group and group.expressions and not tree.find(exp.GroupingSets):
            for g_expr in group.expressions:
                if not any(
                    e.this.sql(dialect="postgres") == g_expr.sql(dialect="postgres")
                    for e in order.expressions
                ):
                    order.expressions.append(exp.Ordered(this=g_expr.copy()))
            query.query = tree.sql(dialect="postgres")
            return

        hint = sorted(unique_cols)[0] if unique_cols else "id"
        order.expressions.append(exp.Ordered(this=exp.Column(this=exp.to_identifier(hint))))
        query.query = tree.sql(dialect="postgres")

    @staticmethod
    def _collect_unique_columns(model: Any) -> set[str]:
        """Estrae l'insieme delle colonne univoche (PK o vincolo UNIQUE) dello schema."""
        unique_cols: set[str] = set()
        for table in model.tables.values():
            if len(table.pk_columns) == 1:
                unique_cols.add(table.pk_columns[0].lower())
            for group in table.unique_groups:
                if len(group) == 1:
                    unique_cols.add(group[0].lower())
        return unique_cols

    @staticmethod
    def _resolve_column_alias(tree: exp.Expression, col_name: str) -> str:
        """Risolve un eventuale alias di proiezione risalendo alla colonna fisica sottostante."""
        for a in tree.find_all(exp.Alias):
            if a.alias.lower() == col_name:
                col_expr = a.this.find(exp.Column)
                if col_expr:
                    return col_expr.name.lower()
        return col_name

    def _validate_ast_rules(
        self, query: GoldQueryDTO, spec: SpecDTO
    ) -> tuple[str, exp.Expression | None]:
        """Verifica la sintassi, l'assenza di schemi espliciti, ORDER BY e feature."""
        try:
            tree = parse_one(query.query, read="postgres")
        except ParseError as pe:
            return f"Errore di sintassi SQL nella Gold Query: {pe}", None

        if self._has_explicit_schema(tree):
            msg = (
                "Qualificazione esplicita dello schema non ammessa "
                "(es. scrivi 'FROM tabella', non 'FROM schema.tabella')."
            )
            return msg, None

        if self._has_star_projection(tree):
            msg = (
                "La query SQL non deve usare proiezioni generiche '*' (es. SELECT *). "
                "Elenca esplicitamente le sole colonne e metriche di business richieste."
            )
            return msg, None

        det_err = self._check_determinism(query, tree)
        if det_err:
            return det_err, None

        feat_res = self._feature_checker.check(tree, spec.sql_features)
        if not feat_res.is_valid:
            msg = (
                f"La query SQL non contiene le seguenti feature obbligatorie richieste: "
                f"{', '.join(feat_res.missing)}."
            )
            return msg, None

        return "", tree

    def _validate_execution(
        self,
        query: GoldQueryDTO,
        schema: str,
        tree: exp.Expression | None,
        profile: DataProfileDTO | None = None,
    ) -> QueryValidationResult:
        """Esegue la query nel sandbox PostgreSQL e valida righe, tabelle e mutazioni."""
        try:
            cols, rows = self._sandbox.run_query(schema, query.query)
        except (DatabaseClientError, PgError) as e:
            msg = ErrorFeedbackBuilder().from_pg_error("Errore di esecuzione SQL in PostgreSQL", e)
            return QueryValidationResult(is_valid=False, error=msg)

        if not rows:
            distinct = self._distinct_from_profile(profile, tree)
            where = self._where_from_tree(tree)
            msg = ErrorFeedbackBuilder().for_empty_result(where, distinct)
            return QueryValidationResult(is_valid=False, error=msg)

        tables = self._tables_used(tree) if tree else []
        if not tables:
            msg = "La query SQL non utilizza alcuna tabella del database."
            return QueryValidationResult(is_valid=False, error=msg)

        mut_res = self._mutation_tester.test(schema, query.query, tables)
        if not mut_res.is_valid:
            distinct = self._distinct_from_profile(profile, tree)
            msg = ErrorFeedbackBuilder().for_mutation(tables, distinct)
            return QueryValidationResult(is_valid=False, error=f"{mut_res.error} | {msg}")

        none_err = find_none_literal([list(r) for r in rows])
        if none_err:
            return QueryValidationResult(is_valid=False, error=none_err)

        gold = self._build_gold(query, cols, rows)
        return QueryValidationResult(is_valid=True, gold_result=gold)

    def _check_determinism(self, query: GoldQueryDTO, tree: exp.Expression) -> str:
        """Verifica le regole di riproducibilità del gold result della query.

        Controlla che un eventuale order_sensitive sia accompagnato da ORDER BY e che
        non compaiano funzioni temporali volatili (CURRENT_DATE, NOW, …).
        """
        if query.order_sensitive and not self._has_root_order_by(tree):
            return (
                "La query ha order_sensitive=true ma manca della clausola ORDER BY "
                "nella query principale della SELECT."
            )
        if tree.find(exp.Limit) and not self._has_root_order_by(tree):
            return (
                "La query usa LIMIT senza ORDER BY nella SELECT principale: le righe "
                "restituite non sarebbero deterministiche. Aggiungi un ORDER BY che definisca "
                "quale sottoinsieme di righe selezionare prima del LIMIT."
            )
        volatile = self._volatile_time_function(tree)
        if volatile:
            return (
                f"La query usa la funzione temporale volatile '{volatile}': il risultato "
                "cambierebbe a ogni esecuzione rendendo il gold non riproducibile. Usa una "
                "data/ora fissa come letterale (es. DATE '2026-08-21') eventualmente combinata "
                "con INTERVAL."
            )
        return ""

    @staticmethod
    def _has_explicit_schema(tree: exp.Expression) -> bool:
        """Verifica se la query contiene riferimenti espliciti a schemi (es. schema.tabella)."""
        return any(t.db or t.catalog for t in tree.find_all(exp.Table))

    @staticmethod
    def _has_star_projection(tree: exp.Expression) -> bool:
        """Verifica se la query SQL principale contiene proiezioni generiche '*' o 'tabella.*'."""
        main_body = tree.this if isinstance(tree, exp.With) else tree
        if isinstance(main_body, exp.Union):
            selects = [main_body.this, main_body.expression]
        elif isinstance(main_body, exp.Select):
            selects = [main_body]
        else:
            selects = list(main_body.find_all(exp.Select))

        for sel in selects:
            if isinstance(sel, exp.Select):
                for expr in sel.expressions:
                    if isinstance(expr, exp.Star):
                        return True
                    if isinstance(expr, exp.Column) and isinstance(expr.this, exp.Star):
                        return True
        return False

    @staticmethod
    def _tables_used(tree: exp.Expression) -> list[str]:
        """Estrae i nomi delle tabelle referenziate nella query."""
        return sorted({t.name for t in find_tables(tree)})

    @staticmethod
    def _has_root_order_by(tree: exp.Expression) -> bool:
        """Verifica che la query SQL contenga la clausola ORDER BY a livello radice."""
        return tree.args.get("order") is not None

    @staticmethod
    def _volatile_time_function(tree: exp.Expression) -> str | None:
        """Ritorna il nome della funzione temporale volatile usata, se presente.

        CURRENT_DATE/NOW e simili rendono il gold result non riproducibile: il solver
        eseguito in un giorno diverso otterrebbe righe diverse per le stesse domande.
        """
        for cls, name in (
            (exp.CurrentDate, "CURRENT_DATE"),
            (exp.CurrentTimestamp, "CURRENT_TIMESTAMP"),
            (exp.CurrentTime, "CURRENT_TIME"),
            (exp.CurrentDatetime, "CURRENT_DATETIME"),
        ):
            if tree.find(cls):
                return name
        if _RE_VOLATILE_TEXT.search(tree.sql(dialect="postgres")):
            return "NOW/LOCALTIMESTAMP"
        return None

    @staticmethod
    def _distinct_from_profile(profile: Any | None, tree: exp.Expression | None) -> dict[str, Any]:
        if profile is None or tree is None:
            return {}
        try:
            data = profile.profile if hasattr(profile, "profile") else {}
            tables = {t.name.lower() for t in tree.find_all(exp.Table)}
            out: dict[str, Any] = {}
            for tname, tdata in data.items():
                if tname.lower() in tables:
                    cols = tdata.get("columns", {})
                    for cname, cdata in cols.items():
                        if cdata.get("distinct", 0) > 1:
                            sample = cdata.get("sample", [])
                            if sample:
                                out[f"{tname}.{cname}"] = sample[0]
                                if len(out) >= _MAX_DISTINCT_SAMPLES:
                                    return out
            return out
        except (AttributeError, TypeError, KeyError, ValueError):
            return {}

    @staticmethod
    def _where_from_tree(tree: exp.Expression | None) -> str | None:
        if tree is None:
            return None
        try:
            where = tree.find(exp.Where)
            return where.sql(dialect="postgres") if where else None
        except (AttributeError, ValueError):
            return None

    @staticmethod
    def _build_gold(query: GoldQueryDTO, cols: list[str], rows: list[tuple]) -> GoldResultDTO:
        """Costruisce un GoldResultDTO con celle temporali canonizzate a forma testuale."""
        return GoldResultDTO(
            columns=cols,
            rows=canonicalize_rows(rows),
            order_sensitive=query.order_sensitive,
        )
