"""Modulo servizio di dominio per la verifica delle feature sintattiche SQL.

:author: Riccardo Morabito
"""

from dataclasses import dataclass, field
from sqlglot import parse_one, exp
from sqlglot.errors import ParseError


@dataclass
class FeatureCheckResult:
    """Esito della verifica delle feature sintattiche SQL richieste."""

    is_valid: bool = True
    missing: list[str] = field(default_factory=list)


class FeatureChecker:
    """Servizio di dominio per la verifica delle feature sintattiche SQL richieste."""

    _CHECKS = {
        "join": lambda t: bool(t.find(exp.Join)),
        "multi_join": lambda t: len(list(t.find_all(exp.Join))) >= 2,
        "self_join": lambda t: _check_self_join(t),
        "scalar_agg": lambda t: bool(t.find(exp.AggFunc)) and t.args.get("group") is None,
        "group_agg": lambda t: bool(t.find(exp.Group)),
        "top_n": lambda t: bool(t.find(exp.Limit)),
        "conjunctive": lambda t: bool(t.find(exp.And)),
        "filtered_agg": lambda t: any(
            f.find(exp.Filter) or f.args.get("filter") or isinstance(f.parent, exp.Filter)
            for f in t.find_all(exp.AggFunc)
        ),
        "having": lambda t: bool(t.find(exp.Having)),
        "subquery": lambda t: len(list(t.find_all(exp.Select))) >= 2,
        "correlated_subquery": lambda t: _check_correlated(t),
        "exists": lambda t: bool(t.find(exp.Exists)),
        "anti_join": lambda t: _check_anti_join(t),
        "set_op": lambda t: bool(t.find(exp.Union, exp.Intersect, exp.Except)),
        "cte": lambda t: bool(t.find(exp.CTE)),
        "recursive_cte": lambda t: bool(t.find(exp.With)) and _is_recursive(t),
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
        missing = [feat for feat in required if not self._CHECKS.get(feat, lambda _: True)(tree)]
        return FeatureCheckResult(is_valid=len(missing) == 0, missing=missing)

    def uses_features(self, query: str | exp.Expression, required: list[str]) -> bool:
        """Restituisce True se la query contiene tutte le feature richieste."""
        return self.check(query, required).is_valid


def _check_self_join(tree: exp.Expression) -> bool:
    """Verifica se la query contiene self-join."""
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE) if c.alias_or_name}
    for select in tree.find_all(exp.Select):
        tables = _direct_tables(select)
        names = [t.name.lower() for t in tables if t.name and t.name.lower() not in cte_names]
        if len(names) != len(set(names)):
            return True
    return False


def _direct_tables(select_node: exp.Select) -> list:
    """Restituisce le tabelle referenziate direttamente da FROM/JOIN in un nodo SELECT."""
    tables = []
    from_clause = select_node.args.get("from")
    if from_clause:
        tables.extend(
            t for t in from_clause.find_all(exp.Table) if t.find_ancestor(exp.Select) is select_node
        )
    for j in select_node.find_all(exp.Join):
        t = j.find(exp.Table)
        if t and t.find_ancestor(exp.Select) is select_node:
            tables.append(t)
    return tables


def _check_anti_join(tree: exp.Expression) -> bool:
    """Verifica se la query contiene anti-join (NOT EXISTS, NOT IN)."""
    has_anti = any("ANTI" in str(j.args.get("kind", "")).upper() for j in tree.find_all(exp.Join))
    has_not = any(isinstance(n.this, (exp.Exists, exp.In)) for n in tree.find_all(exp.Not))
    has_negated = any(bool(n.args.get("is_negated")) for n in tree.find_all(exp.In))
    return has_anti or has_not or has_negated


def _check_correlated(tree: exp.Expression) -> bool:
    """Verifica se la query contiene subquery correlate."""
    selects = list(tree.find_all(exp.Select))
    if len(selects) < 2:
        return False
    root_tables = {t.alias_or_name.lower() for t in selects[0].find_all(exp.Table)}
    for sq in selects[1:]:
        sq_tables = {t.alias_or_name.lower() for t in sq.find_all(exp.Table)}
        outer_tables = root_tables - sq_tables
        if any(c.table and c.table.lower() in outer_tables for c in sq.find_all(exp.Column)):
            return True
    return False


def _is_recursive(tree: exp.Expression) -> bool:
    """Verifica se la WITH RECURSIVE e' presente."""
    with_node = tree.find(exp.With)
    return bool(with_node and with_node.args.get("recursive"))
