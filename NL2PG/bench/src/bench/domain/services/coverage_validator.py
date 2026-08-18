"""Modulo servizio di dominio per la verifica della copertura narrativa delle entita' SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass
from re import compile as re_compile

from dateparser import parse as dateparser_parse
from dateparser.search import search_dates
from sqlglot import exp, find_tables, parse_one
from sqlglot.errors import ParseError

from bench.domain.models.nlp import QuestionDTO, StoryDTO
from bench.domain.models.spec import SpecDTO, TwistRuleDTO
from bench.domain.models.sql import GoldQueryDTO

_MAPPING_TWISTS = frozenset({"rename", "synonym", "jargon", "rephrase", "polysemy"})
_RE_IS_DATE_LIKE = re_compile(r"^\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?$|^\d{1,2}[-/]\d{1,2}[-/]\d{4}$")


@dataclass
class CoverageResult:
    """Esito della verifica di copertura narrativa delle entita' SQL."""

    is_valid: bool = True
    error: str = ""


class CoverageValidator:
    """Servizio di dominio per la verifica che la narrazione copra le entita' della gold query."""

    @staticmethod
    def _map_table_name(name: str, twist_rules: list[TwistRuleDTO]) -> str:
        """Applica il mapping inverso per ricondurre il nome tabella alla forma originale."""
        for rule in twist_rules:
            if (
                rule.twist_type in _MAPPING_TWISTS
                and rule.target_value
                and rule.obsolete_value
                and (rule.target_value.lower() in name or name in rule.target_value.lower())
            ):
                return rule.obsolete_value.lower()
        return name

    @staticmethod
    def _expand_name_variants(name: str) -> set[str]:
        """Espande un identificatore SQL o letterale nelle sue forme narrative equivalenti."""
        raw = name.lower().strip().strip("%_")
        if not raw:
            return set()
        variants = {raw}
        variants.add(raw.replace("_", " "))
        variants.add(raw.replace("-", " "))
        variants.add(raw.replace("_", "-"))
        return variants

    @staticmethod
    def _is_literal_covered(lit: str, text: str) -> bool:
        """Verifica se un valore letterale (testo, pattern LIKE o data) e' presente nella prosa."""
        variants = CoverageValidator._expand_name_variants(lit)
        if any(v in text for v in variants if v):
            return True

        if not _RE_IS_DATE_LIKE.search(lit.strip()):
            return False

        parsed_target = dateparser_parse(lit, settings={"PREFER_DAY_OF_MONTH": "first"})
        if parsed_target:
            try:
                found_dates = search_dates(
                    text,
                    languages=["it"],
                    settings={"PREFER_DAY_OF_MONTH": "first"},
                )
                if found_dates:
                    target_date = parsed_target.date()
                    if any(dt.date() == target_date for _, dt in found_dates):
                        return True
            except (ValueError, TypeError, OverflowError, AttributeError):
                pass

        return False

    @staticmethod
    def _anchors(
        query: GoldQueryDTO | exp.Expression,
        spec: SpecDTO,
        tree: exp.Expression | None = None,
    ) -> tuple[list[str], list[str]]:
        """Estrae nomi tabella e valori letterali dalla gold query, mappando i twist."""
        if tree is None:
            sql_text = query.query if isinstance(query, GoldQueryDTO) else str(query)
            tree = parse_one(sql_text, read="postgres")
        tables = set()
        for t in find_tables(tree):
            mapped = CoverageValidator._map_table_name(t.name.lower(), spec.twist_rules)
            tables.add(mapped)
        literals = set()
        for node_type in (exp.Where, exp.Having, exp.Join):
            for node in tree.find_all(node_type):
                for lit in node.find_all(exp.Literal):
                    if lit.is_string:
                        literals.add(lit.this)
        return sorted(tables), sorted(literals)

    def validate(
        self,
        story: StoryDTO,
        question: QuestionDTO,
        query: GoldQueryDTO | exp.Expression,
        spec: SpecDTO,
        tree: exp.Expression | None = None,
    ) -> CoverageResult:
        """Verifica che story+question copra tabelle e valori letterali della gold query."""
        try:
            tables, literals = self._anchors(query, spec, tree=tree)
        except ParseError as e:
            return CoverageResult(is_valid=False, error=f"AST fallito su query gold: {e}")
        text = (story.story + " " + question.question).lower()
        for ident in tables:
            variants = self._expand_name_variants(ident)
            if not any(v in text for v in variants if v):
                return CoverageResult(
                    is_valid=False,
                    error=(
                        f"Manca la tabella '{ident}' nel testo. "
                        f"DEVI inserire esplicitamente la parola '{ident}' nella prosa."
                    ),
                )
        for lit in literals:
            if not self._is_literal_covered(lit, text):
                return CoverageResult(
                    is_valid=False,
                    error=(
                        f"Manca il valore '{lit}' nel testo. "
                        f"Inserisci il valore '{lit}' nella narrazione."
                    ),
                )
        return CoverageResult()
