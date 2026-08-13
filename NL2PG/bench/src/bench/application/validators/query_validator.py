"""Modulo validatore applicativo per la validazione completa di una gold query SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass

from sqlglot import exp, find_tables, parse_one
from sqlglot.errors import ParseError

from bench.application.validators.mutation_tester import MutationTester
from bench.domain.models.spec import SpecDTO
from bench.domain.models.sql import GoldQueryDTO, GoldResultDTO
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.feature_checker import FeatureChecker


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

    def validate(self, query: GoldQueryDTO, spec: SpecDTO, schema: str) -> QueryValidationResult:
        """Esegue la query, verifica feature e mutazioni, e restituisce il risultato gold."""
        ast_err, tree = self._validate_ast_rules(query, spec)
        if ast_err:
            return QueryValidationResult(is_valid=False, error=ast_err)

        return self._validate_execution(query, schema, tree)

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

        if query.order_sensitive and not self._has_root_order_by(tree):
            msg = (
                "La query ha order_sensitive=true ma manca della clausola ORDER BY "
                "nella query principale della SELECT."
            )
            return msg, None

        feat_res = self._feature_checker.check(tree, spec.sql_features)
        if not feat_res.is_valid:
            msg = (
                f"La query SQL non contiene le seguenti feature obbligatorie richieste: "
                f"{', '.join(feat_res.missing)}."
            )
            return msg, None

        return "", tree

    def _validate_execution(
        self, query: GoldQueryDTO, schema: str, tree: exp.Expression | None
    ) -> QueryValidationResult:
        """Esegue la query nel sandbox PostgreSQL e valida righe, tabelle e mutazioni."""
        try:
            cols, rows = self._sandbox.run_query(schema, query.query)
        except Exception as e:
            msg = f"Errore di esecuzione SQL in PostgreSQL: {e}"
            return QueryValidationResult(is_valid=False, error=msg)

        if not rows:
            msg = (
                "La query ha restituito un risultato vuoto (0 righe). "
                "Inserisci dati o modifica la query in modo da restituire risultati validi."
            )
            return QueryValidationResult(is_valid=False, error=msg)

        tables = self._tables_used(tree) if tree else []
        if not tables:
            msg = "La query SQL non utilizza alcuna tabella del database."
            return QueryValidationResult(is_valid=False, error=msg)

        mut_res = self._mutation_tester.test(schema, query.query, tables)
        if not mut_res.is_valid:
            return QueryValidationResult(is_valid=False, error=mut_res.error)

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
    def _has_root_order_by(tree: exp.Expression) -> bool:
        """Verifica che la query SQL contenga la clausola ORDER BY a livello radice."""
        return tree.args.get("order") is not None

    @staticmethod
    def _build_gold(query: GoldQueryDTO, cols: list[str], rows: list[tuple]) -> GoldResultDTO:
        """Costruisce un GoldResultDTO convertendo le righe in liste di tipi nativi."""
        return GoldResultDTO(
            columns=cols,
            rows=[list(row) for row in rows],
            order_sensitive=query.order_sensitive,
        )
