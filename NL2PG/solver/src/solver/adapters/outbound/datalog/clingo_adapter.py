"""Adattatore outbound per la validazione ed esecuzione di regole Datalog con Clingo.

:author: Riccardo Morabito
"""

from logging import getLogger
from typing import Any

from clingo import (
    Control,
    _internal as clingo_internal,
    ast as clingo_ast,
    backend as clingo_backend,
    configuration as clingo_configuration,
    core as clingo_core,
    statistics as clingo_statistics,
    symbol as clingo_symbol,
    symbolic_atoms as clingo_symbolic_atoms,
    theory_atoms as clingo_theory_atoms,
)

from solver.domain.exceptions import ClingoDependencyError
from solver.domain.ports.outbound.datalog_port import DatalogPort
from solver.domain.services.datalog_utils import DatalogUtils

_log = getLogger("solver.adapters.datalog")


class _ClingoCFFICompatibilityPatcher:
    """Gestore per la compatibilità e decodifica difensiva dei moduli CFFI di Clingo."""

    @staticmethod
    def safe_clingo_to_str(c_str: Any) -> str:
        """Decodifica in modo sicuro le stringhe C di Clingo gestendo byte troncati o non-ASCII."""
        if c_str is None:
            return ""
        ffi = getattr(clingo_internal, "_ffi", None)
        if ffi:
            return ffi.string(c_str).decode("utf-8", errors="replace")
        return str(c_str)

    @staticmethod
    def patch_decoders() -> None:
        """Applica la decodifica difensiva contro UnicodeDecodeError sui moduli CFFI di Clingo."""
        clingo_modules = (
            clingo_internal,
            clingo_core,
            clingo_symbol,
            clingo_ast,
            clingo_backend,
            clingo_configuration,
            clingo_statistics,
            clingo_symbolic_atoms,
            clingo_theory_atoms,
        )
        for mod in clingo_modules:
            if hasattr(mod, "_to_str"):
                setattr(mod, "_to_str", _ClingoCFFICompatibilityPatcher.safe_clingo_to_str)  # noqa: B010


_ClingoCFFICompatibilityPatcher.patch_decoders()


class _ModelSymbolCollector:
    """Raccoglitore di atomi e argomenti per i modelli soddisfacibili di Clingo."""

    def __init__(self, predicate_name: str, results: list[tuple[Any, ...]]) -> None:
        """Salva il nome del predicato target e la lista di destinazione dei risultati."""
        self._predicate_name = predicate_name
        self._results = results

    def __call__(self, model: Any) -> None:
        """Estrae i simboli dal modello e ne converte gli argomenti in tipi nativi."""
        for symbol in model.symbols(shown=True):
            if symbol.name == self._predicate_name:
                args = tuple(
                    DatalogUtils.extract_clingo_symbol_arg(arg) for arg in symbol.arguments
                )
                self._results.append(args)


class ClingoDatalogAdapter(DatalogPort):
    """Adattatore per la validazione ed esecuzione Datalog tramite il solver simbolico Clingo."""

    @staticmethod
    def _null_logger(_code: Any, _message: str) -> None:
        """Silenzia i log C di basso livello di Clingo evitando stampe su stdout/stderr."""
        return

    def validate_syntax(self, datalog_code: str) -> tuple[bool, str]:
        """Valida la sintassi formale delle regole Datalog catturando messaggi diagnostici."""
        diagnostics: list[str] = []

        def _logger(_code: Any, message: str) -> None:
            diagnostics.append(message.strip())

        try:
            ctl = Control(arguments=[], logger=_logger)
            ctl.add("base", [], datalog_code)
            ctl.ground([("base", [])])
            return True, "Sintassi Datalog valida"
        except (RuntimeError, ValueError, TypeError, ClingoDependencyError) as e:
            err_detail = "\n".join(diagnostics) if diagnostics else str(e)
            return False, err_detail

    def run_datalog(
        self,
        facts_datalog: str | list[str],
        rules_datalog: str,
        predicate_name: str = "query",
    ) -> tuple[bool, list[tuple[Any, ...]], str]:
        """Esegue il programma Datalog (fatti + regole) producendo gli atomi della query."""
        diagnostics: list[str] = []

        def _logger(_code: Any, message: str) -> None:
            diagnostics.append(message.strip())

        facts_str = (
            "\n".join(facts_datalog)
            if isinstance(facts_datalog, list)
            else str(facts_datalog or "")
        )

        try:
            ctl = Control(arguments=[], logger=_logger)
            ctl.add("base", [], facts_str + "\n\n" + rules_datalog)
            ctl.ground([("base", [])])

            results: list[tuple[Any, ...]] = []
            collector = _ModelSymbolCollector(predicate_name, results)
            solve_result = ctl.solve(on_model=collector)

            if solve_result.satisfiable or len(results) > 0:
                return True, results, ""
            return True, [], "Modello vuoto o insoddisfacibile"
        except (RuntimeError, ValueError, TypeError, ClingoDependencyError) as e:
            err_detail = "\n".join(diagnostics) if diagnostics else str(e)
            return False, [], err_detail
