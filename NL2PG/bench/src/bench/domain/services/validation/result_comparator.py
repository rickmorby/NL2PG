"""Modulo di dominio puro per il confronto deterministico dei risultati di query SQL.

:author: Riccardo Morabito
"""

from itertools import permutations
from typing import Any

_EPSILON_TOLERANCE = 0.02
_MAX_PERMUTATION_COLS = 8


class ResultComparator:
    """Confronta il risultato candidato con il gold determinando l'equivalenza relazionale."""

    @staticmethod
    def are_values_equivalent(c: Any, g: Any) -> bool:
        """Confronta due valori singoli (stringhe, numeri, float, Decimal, None/null)."""
        if c == g or (c is None and g is None):
            return True

        str_c = str(c).strip().strip('"').lower() if c is not None else "null"
        str_g = str(g).strip().strip('"').lower() if g is not None else "null"
        if str_c == str_g:
            return True

        try:
            cf, gf = float(c), float(g)
            return (
                round(cf, 4) == round(gf, 4)
                or abs(cf - gf) <= _EPSILON_TOLERANCE
                or round(cf / 100.0, 4) == round(gf, 4)
                or abs(cf / 100.0 - gf) <= _EPSILON_TOLERANCE
                or round(cf, 4) == round(gf / 100.0, 4)
                or abs(cf - gf / 100.0) <= _EPSILON_TOLERANCE
            )
        except (ValueError, TypeError):
            return False

    def compare(
        self,
        candidate_rows: list[list[Any]] | list[tuple[Any, ...]],
        gold_rows: list[list[Any]] | list[tuple[Any, ...]],
        order_sensitive: bool = False,
    ) -> bool:
        """Determina se le righe candidate equivalgono alle righe gold (anche per permutazione)."""
        if len(candidate_rows) != len(gold_rows):
            return False
        if not candidate_rows and not gold_rows:
            return True
        if len(candidate_rows[0]) != len(gold_rows[0]):
            return False

        num_cols = len(gold_rows[0])

        if self._check_rows_match(candidate_rows, gold_rows, order_sensitive):
            return True

        if num_cols <= _MAX_PERMUTATION_COLS:
            for perm in permutations(range(num_cols)):
                permuted_cand = [[row[i] for i in perm] for row in candidate_rows]
                if self._check_rows_match(permuted_cand, gold_rows, order_sensitive):
                    return True

        return False

    @staticmethod
    def _check_rows_match(
        cand: list[list[Any]] | list[tuple[Any, ...]],
        gold: list[list[Any]] | list[tuple[Any, ...]],
        order_sensitive: bool,
    ) -> bool:
        """Verifica se due insiemi di righe corrispondono direttamente o come multiset."""
        if order_sensitive:
            return all(
                all(
                    ResultComparator.are_values_equivalent(cv, gv)
                    for cv, gv in zip(c, g, strict=False)
                )
                for c, g in zip(cand, gold, strict=False)
            )

        unmatched = list(gold)
        for c in cand:
            found_idx = None
            for idx, g in enumerate(unmatched):
                if all(
                    ResultComparator.are_values_equivalent(cv, gv)
                    for cv, gv in zip(c, g, strict=False)
                ):
                    found_idx = idx
                    break
            if found_idx is None:
                return False
            unmatched.pop(found_idx)

        return len(unmatched) == 0
