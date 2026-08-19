"""Modulo servizio di dominio per la verifica delle feature sintattiche SQL richieste.

:author: Riccardo Morabito
"""

from dataclasses import dataclass, field
from typing import ClassVar

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

_MIN_MULTI_COUNT = 2


@dataclass
class FeatureCheckResult:
    """Esito della verifica delle feature sintattiche SQL richieste."""

    is_valid: bool = True
    missing: list[str] = field(default_factory=list)


class FeatureChecker:
    """Servizio di dominio per la verifica delle feature sintattiche SQL richieste."""

    @staticmethod
    def _direct_tables(select_node: exp.Select) -> list:
        """Restituisce le tabelle referenziate direttamente da FROM/JOIN in un nodo SELECT."""
        tables = []
        from_clause = select_node.args.get("from_") or select_node.args.get("from")
        if from_clause:
            tables.extend(
                t
                for t in from_clause.find_all(exp.Table)
                if t.find_ancestor(exp.Select) is select_node
            )
        for j in select_node.find_all(exp.Join):
            t = j.find(exp.Table)
            if t and t.find_ancestor(exp.Select) is select_node:
                tables.append(t)
        return tables

    @staticmethod
    def _check_self_join(tree: exp.Expression) -> bool:
        """Verifica se la query contiene self-join (sia su tabelle fisiche che su CTE)."""
        for select in tree.find_all(exp.Select):
            tables = FeatureChecker._direct_tables(select)
            names = [t.name.lower() for t in tables if t.name]
            if len(names) != len(set(names)):
                return True
        return False

    @staticmethod
    def _check_anti_join(tree: exp.Expression) -> bool:
        """Verifica se la query contiene anti-join (NOT EXISTS, NOT IN)."""
        has_anti = any(
            "ANTI" in str(j.args.get("kind", "")).upper() for j in tree.find_all(exp.Join)
        )
        has_not = any(isinstance(n.this, (exp.Exists, exp.In)) for n in tree.find_all(exp.Not))
        has_negated = any(bool(n.args.get("is_negated")) for n in tree.find_all(exp.In))
        return has_anti or has_not or has_negated

    @staticmethod
    def _check_correlated(tree: exp.Expression) -> bool:
        """Verifica se la query contiene subquery correlate."""
        selects = list(tree.find_all(exp.Select))
        if len(selects) < _MIN_MULTI_COUNT:
            return False
        root_tables = {t.alias_or_name.lower() for t in selects[0].find_all(exp.Table)}
        for sq in selects[1:]:
            sq_tables = {t.alias_or_name.lower() for t in sq.find_all(exp.Table)}
            outer_tables = root_tables - sq_tables
            if any(c.table and c.table.lower() in outer_tables for c in sq.find_all(exp.Column)):
                return True
        return False

    @staticmethod
    def _is_recursive(tree: exp.Expression) -> bool:
        """Verifica se la WITH RECURSIVE e' presente."""
        with_node = tree.find(exp.With)
        return bool(with_node and with_node.args.get("recursive"))

    _CHECKS: ClassVar = {
        "join": lambda t: bool(t.find(exp.Join)),
        "multi_join": lambda t: len(list(t.find_all(exp.Join))) >= _MIN_MULTI_COUNT,
        "self_join": _check_self_join,
        "scalar_agg": lambda t: bool(t.find(exp.AggFunc)) and t.args.get("group") is None,
        "group_agg": lambda t: bool(t.find(exp.Group)),
        "top_n": lambda t: bool(t.find(exp.Limit)),
        "conjunctive": lambda t: bool(t.find(exp.And)),
        "filtered_agg": lambda t: any(
            f.find(exp.Filter) or f.args.get("filter") or isinstance(f.parent, exp.Filter)
            for f in t.find_all(exp.AggFunc)
        ),
        "having": lambda t: bool(t.find(exp.Having)),
        "subquery": lambda t: len(list(t.find_all(exp.Select))) >= _MIN_MULTI_COUNT,
        "correlated_subquery": _check_correlated,
        "exists": lambda t: bool(t.find(exp.Exists)),
        "anti_join": _check_anti_join,
        "set_op": lambda t: bool(t.find(exp.Union, exp.Intersect, exp.Except)),
        "cte": lambda t: bool(t.find(exp.CTE)),
        "recursive_cte": lambda t: bool(t.find(exp.With)) and FeatureChecker._is_recursive(t),
        "window": lambda t: bool(t.find(exp.Window)),
        "lateral": lambda t: bool(t.find(exp.Lateral)),
        "full_outer_join": lambda t: any(
            str(j.args.get("side", "")).upper() == "FULL" for j in t.find_all(exp.Join)
        ),
        "right_outer_join": lambda t: any(
            str(j.args.get("side", "")).upper() == "RIGHT" for j in t.find_all(exp.Join)
        ),
        "left_outer_join": lambda t: any(
            str(j.args.get("side", "")).upper() == "LEFT" for j in t.find_all(exp.Join)
        ),
        "cross_join": lambda t: any(
            str(j.args.get("kind", "")).upper() == "CROSS" for j in t.find_all(exp.Join)
        ),
        "distinct_on": lambda t: any(d.args.get("on") for d in t.find_all(exp.Distinct)),
        "natural_join": lambda t: any(
            str(j.args.get("method", "")).upper() == "NATURAL" for j in t.find_all(exp.Join)
        ),
        "sorting": lambda t: t.args.get("order") is not None,
        "distinct": lambda t: bool(t.find(exp.Distinct)),
        "agg_distinct": lambda t: any(
            isinstance(a.args.get("this"), exp.Distinct) for a in t.find_all(exp.AggFunc)
        ),
        "is_distinct_from": lambda t: bool(t.find(exp.NullSafeNEQ)),
        "between": lambda t: bool(t.find(exp.Between)),
        "in_condition": lambda t: bool(t.find(exp.In)),
        "is_null": lambda t: any(isinstance(i.expression, exp.Null) for i in t.find_all(exp.Is)),
        "disjunctive": lambda t: bool(t.find(exp.Or)),
        "like": lambda t: bool(t.find(exp.Like)),
        "any_all": lambda t: bool(t.find(exp.Any, exp.All)),
        "relative_time": lambda t: bool(
            t.find(exp.CurrentDate, exp.CurrentTimestamp, exp.CurrentTime, exp.Interval)
        ),
        "overlaps": lambda t: bool(t.find(exp.Overlaps)),
        "offset_fetch": lambda t: bool(t.find(exp.Offset, exp.Fetch)),
        "ordered_set_agg": lambda t: bool(
            t.find(exp.PercentileCont, exp.PercentileDisc, exp.WithinGroup)
        ),
        "grouping_sets": lambda t: bool(t.find(exp.GroupingSets)),
        "row_types": lambda t: bool(t.find(exp.Tuple)),
        "values": lambda t: bool(t.find(exp.Values)),
        "case": lambda t: bool(t.find(exp.Case)),
        "string_funcs": lambda t: bool(
            t.find(
                exp.Upper,
                exp.Lower,
                exp.Concat,
                exp.Substring,
                exp.Trim,
                exp.Replace,
                exp.Initcap,
                exp.Length,
            )
        ),
        "math_funcs": lambda t: bool(
            t.find(
                exp.Round,
                exp.Abs,
                exp.Pow,
                exp.Mod,
                exp.Ceil,
                exp.Floor,
                exp.Sqrt,
                exp.Exp,
                exp.Ln,
                exp.Log,
            )
        ),
        "cast": lambda t: bool(t.find(exp.Cast, exp.TryCast)),
        "boolean_predicate": lambda t: any(
            isinstance(i.expression, exp.Boolean) for i in t.find_all(exp.Is)
        ),
    }

    def check(self, query: str | exp.Expression, required: list[str]) -> FeatureCheckResult:
        """Verifica che la query SQL contenga tutte le feature richieste."""
        if isinstance(query, exp.Expression):
            tree = query
        else:
            try:
                tree = parse_one(query, read="postgres")
            except ParseError:
                return FeatureCheckResult(is_valid=False, missing=required)

        missing = [
            feat for feat in required if feat not in self._CHECKS or not self._CHECKS[feat](tree)
        ]
        return FeatureCheckResult(is_valid=len(missing) == 0, missing=missing)
