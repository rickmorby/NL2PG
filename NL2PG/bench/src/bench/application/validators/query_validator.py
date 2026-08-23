"""Modulo validatore applicativo per la validazione completa di una gold query SQL.

Compone tre verifiche in pipeline: regole AST (sintassi, stile, feature,
determinismo), esecuzione nel sandbox PostgreSQL con feedback arricchito e
costruzione del gold result canonizzato.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from typing import Any

from psycopg.errors import Error as PgError
from sqlglot import exp, find_tables, parse_one
from sqlglot.errors import ParseError

from bench.application.validators.determinism_checker import (
    check_determinism,
)
from bench.application.validators.mutation_tester import MutationTester
from bench.domain.exceptions import DatabaseClientError
from bench.domain.models.data import DataProfileDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.models.sql import GoldQueryDTO, GoldResultDTO
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.validation.error_feedback_builder import ErrorFeedbackBuilder
from bench.domain.services.validation.feature_checker import FeatureChecker
from bench.domain.services.validation.gold_normalizer import canonicalize_rows, find_none_literal
from bench.domain.services.validation.tiebreaker import (
    ensure_tiebreaker,
)

_MAX_DISTINCT_SAMPLES = 2


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
            ensure_tiebreaker(query, tree, schema, self._sandbox)

        return self._validate_execution(query, schema, tree, profile)

    def ensure_tiebreaker(self, query: GoldQueryDTO, schema: str) -> GoldQueryDTO:
        """API pubblica: garantisce l'ORDER BY univoco (usato alla promozione D1)."""
        try:
            tree = parse_one(query.query, read="postgres")
        except ParseError:
            return query
        ensure_tiebreaker(query, tree, schema, self._sandbox)
        return query

    def _validate_ast_rules(
        self, query: GoldQueryDTO, spec: SpecDTO
    ) -> tuple[str, exp.Expression | None]:
        """Verifica la sintassi, l'assenza di schemi espliciti, ORDER BY e feature."""
        try:
            tree = parse_one(query.query, read="postgres")
        except ParseError as pe:
            return f"Errore di sintassi SQL nella Gold Query: {pe}", None

        if any(t.db or t.catalog for t in tree.find_all(exp.Table)):
            msg = (
                "Qualificazione esplicita dello schema non ammessa "
                "(es. scrivi 'FROM tabella', non 'FROM schema.tabella')."
            )
            return msg, None

        if _has_star_projection(tree):
            msg = (
                "La query SQL non deve usare proiezioni generiche '*' (es. SELECT *). "
                "Elenca esplicitamente le sole colonne e metriche di business richieste."
            )
            return msg, None

        det_err = check_determinism(query.order_sensitive, tree)
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
            distinct = _distinct_from_profile(profile, tree)
            msg = ErrorFeedbackBuilder().for_empty_result(_where_from_tree(tree), distinct)
            return QueryValidationResult(is_valid=False, error=msg)

        tables = sorted({t.name for t in find_tables(tree)}) if tree else []
        if not tables:
            msg = "La query SQL non utilizza alcuna tabella del database."
            return QueryValidationResult(is_valid=False, error=msg)

        mut_res = self._mutation_tester.test(schema, query.query, tables)
        if not mut_res.is_valid:
            distinct = _distinct_from_profile(profile, tree)
            msg = ErrorFeedbackBuilder().for_mutation(tables, distinct)
            return QueryValidationResult(is_valid=False, error=f"{mut_res.error} | {msg}")

        none_err = find_none_literal([list(r) for r in rows])
        if none_err:
            return QueryValidationResult(is_valid=False, error=none_err)

        gold = GoldResultDTO(
            columns=cols,
            rows=canonicalize_rows(rows),
            order_sensitive=query.order_sensitive,
        )
        return QueryValidationResult(is_valid=True, gold_result=gold)


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


def _distinct_from_profile(
    profile: DataProfileDTO | None, tree: exp.Expression | None
) -> dict[str, Any]:
    """Campiona valori distinti dal profilo per le tabelle referenziate dalla query."""
    if profile is None or tree is None:
        return {}
    try:
        data = profile.profile if hasattr(profile, "profile") else {}
        tables = {t.name.lower() for t in tree.find_all(exp.Table)}
        out: dict[str, Any] = {}
        for tname, tdata in data.items():
            if tname.lower() not in tables:
                continue
            for cname, cdata in tdata.get("columns", {}).items():
                if cdata.get("distinct", 0) > 1 and cdata.get("sample"):
                    out[f"{tname}.{cname}"] = cdata["sample"][0]
                    if len(out) >= _MAX_DISTINCT_SAMPLES:
                        return out
        return out
    except (AttributeError, TypeError, KeyError, ValueError):
        return {}


def _where_from_tree(tree: exp.Expression | None) -> str | None:
    """Restituisce la clausola WHERE serializzata, se presente."""
    if tree is None:
        return None
    try:
        where = tree.find(exp.Where)
        return where.sql(dialect="postgres") if where else None
    except (AttributeError, ValueError):
        return None
