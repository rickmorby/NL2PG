"""Servizio di dominio puro per il calcolo delle metriche statistiche e profondità AST.

:author: Riccardo Morabito
"""

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlglot import parse_one
from sqlglot.errors import ParseError

from bench.domain.models.analytics import AnalyticsDTO


class AnalyticsCalculator:
    """Servizio di dominio per il calcolo delle aggregazioni statistiche e analisi AST."""

    def compute_metrics(self, tasks: list[dict[str, Any]], run_id: str) -> AnalyticsDTO:
        """Calcola gli aggregati statistici scientifici dai task."""
        total = len(tasks)
        diff_dist = Counter(t.get("difficulty", {}).get("label", "unknown") for t in tasks)
        dom_dist = Counter(
            t.get("spec", {}).get("domain", "unknown") for t in tasks if t.get("spec")
        )

        feat_counts: Counter = Counter()
        twist_counts: Counter = Counter()
        pass_rates = []

        for t in tasks:
            spec = t.get("spec") or {}
            for f in spec.get("sql_features", []):
                feat_counts[f] += 1
            for tr in spec.get("twist_rules", []):
                twist_counts[tr.get("twist_type", "unknown")] += 1

            diff = t.get("difficulty") or {}
            pr = diff.get("calibration_pass_rate")
            if pr is not None:
                pass_rates.append(float(pr))

        avg_pr = round(sum(pass_rates) / len(pass_rates), 4) if pass_rates else 0.0

        return AnalyticsDTO(
            run_id=run_id,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            total_tasks=total,
            difficulty_distribution=dict(diff_dist),
            domain_distribution=dict(dom_dist),
            sql_feature_counts=dict(feat_counts),
            twist_type_counts=dict(twist_counts),
            avg_pass_rate=avg_pr,
        )

    def parse_depth(self, query: str) -> int:
        """Calcola la profondità dell'albero AST sqlglot per una query SQL."""
        try:
            tree = parse_one(query, read="postgres")
            return self._tree_depth(tree)
        except (ParseError, ValueError, AttributeError):
            return 3

    def _tree_depth(self, node: Any) -> int:
        """Calcola ricorsivamente la profondità massima di un nodo AST."""
        if node is None or not hasattr(node, "args"):
            return 1
        max_d = 0
        for child in node.args.values():
            if isinstance(child, list):
                for item in child:
                    max_d = max(max_d, self._tree_depth(item))
            elif child is not None:
                max_d = max(max_d, self._tree_depth(child))
        return 1 + max_d
