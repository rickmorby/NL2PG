"""Modulo validatore applicativo per la validazione completa di una gold query SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from logging import getLogger

from sqlglot import exp, find_tables, parse_one
from sqlglot.errors import ParseError

from bench.application.validators.mutation_tester import MutationTester
from bench.domain.models.spec import SpecDTO
from bench.domain.models.sql import GoldQueryDTO, GoldResultDTO
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.feature_checker import FeatureChecker
from bench.domain.services.sql_repair import PostgresSQLRepair

_log = getLogger("bench.application.validators")


@dataclass
class QueryValidationResult:
    """Esito della validazione completa di una gold query."""

    is_valid: bool = True
    error: str = ""
    gold_result: GoldResultDTO | None = None
    repaired_query: GoldQueryDTO | None = None


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
        self._repair = PostgresSQLRepair()
        self._max_group_by_repairs = 3

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
        """Esegue la query nel sandbox PostgreSQL riparando i GROUP BY mancanti.

        Quando PostgreSQL segnala una colonna non aggregata assente dal GROUP BY, la
        colonna viene aggiunta deterministicamente e la query rieseguita (fino a
        `_max_group_by_repairs` volte). Se la riparazione non è possibile o introduce
        un errore diverso, si interrompe restituendo il feedback originale al retry
        dell'agente.
        """
        executed_query = query.query
        repairs = 0
        while True:
            try:
                cols, rows = self._sandbox.run_query(schema, executed_query)
            except Exception as e:
                msg = str(e)
                if repairs >= self._max_group_by_repairs:
                    return QueryValidationResult(
                        is_valid=False, error=f"Errore di esecuzione SQL in PostgreSQL: {msg}"
                    )
                repaired = self._repair.repair_group_by(executed_query, msg)
                if repaired == executed_query:
                    return QueryValidationResult(
                        is_valid=False, error=f"Errore di esecuzione SQL in PostgreSQL: {msg}"
                    )
                executed_query = repaired
                repairs += 1
                _log.info(
                    "Riparazione deterministica GROUP BY (%d/%d): %s",
                    repairs,
                    self._max_group_by_repairs,
                    msg[:100],
                )
                continue
            break

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

        mut_res = self._mutation_tester.test(schema, executed_query, tables)
        if not mut_res.is_valid:
            return QueryValidationResult(is_valid=False, error=mut_res.error)

        gold = self._build_gold(query, cols, rows)
        repaired_query = (
            GoldQueryDTO(
                query=executed_query, intent=query.intent, order_sensitive=query.order_sensitive
            )
            if executed_query != query.query
            else None
        )
        return QueryValidationResult(is_valid=True, gold_result=gold, repaired_query=repaired_query)

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
