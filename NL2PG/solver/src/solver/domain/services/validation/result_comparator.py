"""Confronto candidato-vs-gold con semantica di ordine a gruppi di parita'.

Con ``order_sensitive=False`` il risultato e' confrontato come multinsieme.
Con ``order_sensitive=True`` e chiavi di parita' note, i gruppi ORDER BY restano
in posizione ma le righe dentro lo stesso gruppo possono scambiarsi. Questo riflette
il non-determinismo SQL quando la chiave di ordinamento non e' univoca.

Lo scaling numerico e' consentito esclusivamente in direzione Datalog -> SQL:
il candidato puo' essere un intero x1000, il gold resta nel valore PostgreSQL.

:author: Riccardo Morabito
"""

from datetime import date, datetime
from itertools import permutations
from re import compile as re_compile
from typing import Any

from solver.domain.services.datalog_numeric import DEFAULT_SCALE

_EPSILON_TOLERANCE = 0.02
_MAX_PERMUTATION_COLS = 8
_MIN_PERMUTATION_COLS = 2

_RE_TIMESTAMP_SEP = re_compile(r"(\d{4}-\d{2}-\d{2})[Tt ](\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)")


def _canonical_value(value: Any) -> Any:
    """Riduce date e datetime alla forma serializzata dal driver PostgreSQL."""
    return str(value) if isinstance(value, (date, datetime)) else value


def _text_value(value: Any) -> str:
    """Normalizza un valore non numerico per il confronto."""
    text = str(value).strip().strip('"').lower() if value is not None else "null"
    return _RE_TIMESTAMP_SEP.sub(r"\1 \2", text)


class ResultComparator:
    """Confronta risultati SQL e Datalog con regole esplicite di permissivita'."""

    @staticmethod
    def are_values_equivalent(
        candidate: Any,
        gold: Any,
        allow_scaling: bool = False,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Confronta due celle, con scala Datalog opzionale e unidirezionale."""
        candidate = _canonical_value(candidate)
        gold = _canonical_value(gold)
        if candidate == gold or (candidate is None and gold is None):
            return True
        if _text_value(candidate) == _text_value(gold):
            return True
        try:
            candidate_number = float(candidate)
            gold_number = float(gold)
        except (TypeError, ValueError):
            return False
        if abs(candidate_number - gold_number) <= _EPSILON_TOLERANCE:
            return True
        return allow_scaling and (abs(candidate_number / scale - gold_number) <= _EPSILON_TOLERANCE)

    def compare(
        self,
        candidate_rows: list[list[Any]] | list[tuple[Any, ...]],
        gold_rows: list[list[Any]] | list[tuple[Any, ...]],
        order_sensitive: bool = False,
        tie_keys: list[int] | None = None,
        candidate_columns: list[str] | None = None,
        gold_columns: list[str] | None = None,
        allow_scaling: bool = False,
        dedup_gold: bool = False,
        allow_column_permutation: bool = False,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Determina l'equivalenza relazionale secondo la policy di ordinamento."""
        candidate = [list(row) for row in candidate_rows]
        gold = self._deduplicate(gold_rows) if dedup_gold else [list(row) for row in gold_rows]
        aligned = self._align_columns(candidate, candidate_columns, gold_columns)
        if aligned is None or len(aligned) != len(gold):
            return False
        if not aligned:
            return not gold
        if len(aligned[0]) != len(gold[0]):
            return False
        if order_sensitive:
            return self._ordered_match(aligned, gold, tie_keys, allow_scaling, scale)
        if self._multiset_match(aligned, gold, allow_scaling, scale):
            return True
        return self._unordered_fallback(
            aligned, gold, allow_scaling, scale, allow_column_permutation
        )

    def _unordered_fallback(
        self,
        aligned: list[list[Any]],
        gold: list[list[Any]],
        allow_scaling: bool,
        scale: int,
        allow_column_permutation: bool,
    ) -> bool:
        """Fallback del confronto non ordinato: permutazione colonne se ammessa."""
        if not allow_column_permutation:
            return False
        return self._permuted_match(aligned, gold, allow_scaling, scale)

    @staticmethod
    def _deduplicate(rows: list[list[Any]] | list[tuple[Any, ...]]) -> list[list[Any]]:
        """Deduplica il gold per la semantica insiemistica del Datalog."""
        unique: list[list[Any]] = []
        for row in rows:
            normalized = list(row)
            if not any(ResultComparator._row_exact(normalized, known) for known in unique):
                unique.append(normalized)
        return unique

    @staticmethod
    def _row_exact(left: list[Any], right: list[Any]) -> bool:
        """Confronto esatto normalizzato, usato solo per deduplicare il gold."""
        return len(left) == len(right) and all(
            _text_value(value_left) == _text_value(value_right)
            for value_left, value_right in zip(left, right, strict=True)
        )

    @staticmethod
    def _align_columns(
        rows: list[list[Any]],
        candidate_columns: list[str] | None,
        gold_columns: list[str] | None,
    ) -> list[list[Any]] | None:
        """Allinea le colonne per nome quando entrambi gli insiemi di nomi sono noti."""
        if not candidate_columns or not gold_columns:
            return rows
        candidate_names = [name.strip().lower() for name in candidate_columns]
        gold_names = [name.strip().lower() for name in gold_columns]
        if len(candidate_names) != len(gold_names) or sorted(candidate_names) != sorted(gold_names):
            return None
        order = [candidate_names.index(name) for name in gold_names]
        return [[row[index] for index in order] for row in rows]

    def _ordered_match(
        self,
        candidate: list[list[Any]],
        gold: list[list[Any]],
        tie_keys: list[int] | None,
        allow_scaling: bool,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Confronta l'ordine, permettendo permutazioni dentro i soli gruppi di parita'."""
        if not tie_keys:
            return self._positional_match(candidate, gold, allow_scaling, scale)
        cursor = 0
        for group in self._tie_groups(gold, tie_keys):
            candidate_group = candidate[cursor : cursor + len(group)]
            if not self._multiset_match(candidate_group, group, allow_scaling, scale):
                return False
            cursor += len(group)
        return cursor == len(candidate)

    @staticmethod
    def _tie_groups(rows: list[list[Any]], tie_keys: list[int]) -> list[list[list[Any]]]:
        """Raggruppa righe gold consecutive con uguale chiave ORDER BY."""
        groups: list[list[list[Any]]] = []
        for row in rows:
            key = tuple(_text_value(row[index]) for index in tie_keys if index < len(row))
            if groups and key == ResultComparator._tie_key(groups[-1][0], tie_keys):
                groups[-1].append(row)
            else:
                groups.append([row])
        return groups

    @staticmethod
    def _tie_key(row: list[Any], tie_keys: list[int]) -> tuple[str, ...]:
        """Chiave normalizzata di una riga per le sole colonne ORDER BY."""
        return tuple(_text_value(row[index]) for index in tie_keys if index < len(row))

    def _multiset_match(
        self,
        candidate: list[list[Any]],
        gold: list[list[Any]],
        allow_scaling: bool,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Confronto a multinsieme senza assumere alcun ordinamento."""
        if len(candidate) != len(gold):
            return False
        unmatched = list(gold)
        for candidate_row in candidate:
            index = self._matching_row_index(candidate_row, unmatched, allow_scaling, scale)
            if index is None:
                return False
            unmatched.pop(index)
        return not unmatched

    def _matching_row_index(
        self,
        candidate: list[Any],
        options: list[list[Any]],
        allow_scaling: bool,
        scale: int = DEFAULT_SCALE,
    ) -> int | None:
        """Indice della prima riga gold semanticamente uguale al candidato."""
        for index, gold in enumerate(options):
            if self._rows_match(candidate, gold, allow_scaling, scale):
                return index
        return None

    def _rows_match(
        self,
        candidate: list[Any],
        gold: list[Any],
        allow_scaling: bool,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Confronta due righe rispettando l'ordine delle colonne."""
        return len(candidate) == len(gold) and all(
            self.are_values_equivalent(value_candidate, value_gold, allow_scaling, scale)
            for value_candidate, value_gold in zip(candidate, gold, strict=True)
        )

    def _positional_match(
        self,
        candidate: list[list[Any]],
        gold: list[list[Any]],
        allow_scaling: bool,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Confronto strettamente posizionale quando non sono note chiavi di parita'."""
        return len(candidate) == len(gold) and all(
            self._rows_match(candidate_row, gold_row, allow_scaling, scale)
            for candidate_row, gold_row in zip(candidate, gold, strict=True)
        )

    def _permuted_match(
        self,
        candidate: list[list[Any]],
        gold: list[list[Any]],
        allow_scaling: bool,
        scale: int = DEFAULT_SCALE,
    ) -> bool:
        """Fallback esplicito e limitato per risposte senza metadati di colonna."""
        width = len(gold[0])
        if not _MIN_PERMUTATION_COLS <= width <= _MAX_PERMUTATION_COLS:
            return False
        for order in permutations(range(width)):
            permuted = [[row[index] for index in order] for row in candidate]
            if self._multiset_match(permuted, gold, allow_scaling, scale):
                return True
        return False
