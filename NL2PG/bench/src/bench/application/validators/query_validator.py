"""Modulo validatore applicativo per la validazione completa di una gold query SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from sqlglot import exp, find_tables, parse_one
from sqlglot.errors import ParseError
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.models.sql import GoldQueryDTO, GoldResultDTO
from bench.domain.models.spec import SpecDTO
from bench.domain.services.feature_checker import FeatureChecker
from bench.application.validators.mutation_tester import MutationTester


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
        self, query: GoldQueryDTO, spec: SpecDTO, schema: str
    ) -> QueryValidationResult:
        """Esegue la query, verifica feature e mutazioni, e restituisce il risultato gold."""
        try:
            tree = parse_one(query.query, read="postgres")
        except ParseError as pe:
            return QueryValidationResult(
                is_valid=False, error=f"Errore di sintassi SQL nella Gold Query: {pe}"
            )

        if self._has_explicit_schema(tree):
            return QueryValidationResult(
                is_valid=False,
                error=(
                    "Qualificazione esplicita dello schema non ammessa "
                    "(es. scrivi 'FROM tabella', non 'FROM schema.tabella')."
                ),
            )
        try:
            cols, rows = self._sandbox.run_query(schema, query.query)
        except Exception as e:
            return QueryValidationResult(
                is_valid=False, error=f"Errore di esecuzione SQL in PostgreSQL: {e}"
            )
        if not rows:
            return QueryValidationResult(
                is_valid=False,
                error=(
                    "La query ha restituito un risultato vuoto (0 righe). "
                    "Inserisci dati o modifica la query in modo da restituire risultati validi."
                ),
            )
        if query.order_sensitive and not self._order_by_root_only(tree, query.order_sensitive):
            return QueryValidationResult(
                is_valid=False,
                error=(
                    "La query ha order_sensitive=true ma manca della clausola ORDER BY "
                    "nella query principale della SELECT."
                ),
            )
        feat_result = self._feature_checker.check(tree, spec.sql_features)
        if not feat_result.is_valid:
            return QueryValidationResult(
                is_valid=False,
                error=(
                    f"La query SQL non contiene le seguenti feature obbligatorie richieste: "
                    f"{', '.join(feat_result.missing)}."
                ),
            )
        tables = self._tables_used(tree)
        if not tables:
            return QueryValidationResult(
                is_valid=False,
                error="La query SQL non utilizza alcuna tabella del database.",
            )
        mut_result = self._mutation_tester.test(schema, query.query, tables)
        if not mut_result.is_valid:
            return QueryValidationResult(is_valid=False, error=mut_result.error)
        gold = self._build_gold(query, cols, rows)
        return QueryValidationResult(is_valid=True, gold_result=gold)

    @staticmethod
    def _has_explicit_schema(tree: exp.Expression) -> bool:
        """Verifica se la query contiene riferimenti espliciti a schemi (es. schema.tabella)."""
        return any(t.db or t.catalog for t in tree.find_all(exp.Table))

    @staticmethod
    def _tables_used(tree: exp.Expression) -> list[str]:
        """Estrae i nomi delle tabelle referenziate nella query."""
        return sorted({t.name for t in find_tables(tree)})

    @staticmethod
    def _order_by_root_only(tree: exp.Expression, order_sensitive: bool) -> bool:
        """Verifica che le query order_sensitive abbiano ORDER BY a livello radice."""
        if not order_sensitive:
            return True
        return tree.args.get("order") is not None

    @staticmethod
    def _build_gold(
        query: GoldQueryDTO, cols: list[str], rows: list[tuple]
    ) -> GoldResultDTO:
        """Costruisce un GoldResultDTO memorizzando le righe in formato nativo Python."""
        raw_rows = [list(r) for r in rows]
        return GoldResultDTO(
            columns=cols, rows=raw_rows, order_sensitive=query.order_sensitive
        )






