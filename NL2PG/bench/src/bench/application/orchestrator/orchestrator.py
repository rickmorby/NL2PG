"""Modulo orchestrator per la pipeline di generazione basata su LangGraph.

:author: Riccardo Morabito
"""

from logging import getLogger
from typing import Any, Callable
from uuid import uuid4
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from bench.application.agents.base import AbstractAgent
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.repository_port import MetaRepositoryPort
from bench.domain.ports.outbound.sandbox_port import SandboxPort
from bench.domain.services.coverage_validator import CoverageValidator
from bench.domain.services.weighted_mean import weighted_mean

_log = getLogger("bench.orchestrator")


class Orchestrator:
    """Costruisce ed esegue il grafo LangGraph della pipeline di generazione."""

    def __init__(
        self,
        sandbox: SandboxPort,
        config: ConfigPort,
        meta_repo: MetaRepositoryPort,
        agents: dict[str, AbstractAgent],
    ) -> None:
        """Inietta le dipendenze di infrastruttura e costruisce il grafo."""
        self._sandbox = sandbox
        self._config = config
        self._meta_repo = meta_repo
        self._agents = agents
        self._coverage = CoverageValidator()
        self._graph_builder = self._build_graph()

    def run_task(self, initial: TaskStateDTO, run_id: str) -> TaskStateDTO:
        """Esegue un task della pipeline con schema temporaneo e checkpoint."""
        task_id = f"nl2pg-{uuid4().hex[:12]}"
        state = initial.model_copy(update={"task_id": task_id, "run_id": run_id})
        with self._sandbox.task_scope() as schema:
            state = state.model_copy(update={"sandbox_schema": schema})
            config: dict[str, Any] = {
                "configurable": {"thread_id": task_id},
                "recursion_limit": 60,
            }
            graph = self._graph_builder.compile(checkpointer=MemorySaver())
            try:
                result = graph.invoke(state, config=config)
                return TaskStateDTO.model_validate(result)
            except Exception as e:
                failed = self._recover_state(graph, config, state)
                return failed.model_copy(
                    update={
                        "verdict": "failed",
                        "last_error": f"{type(e).__name__}: {e}",
                    }
                )

    def _recover_state(
        self, graph: Any, config: dict[str, Any], fallback: TaskStateDTO
    ) -> TaskStateDTO:
        """Recupera l'ultimo stato valido dal checkpoint o restituisce il fallback."""
        try:
            snap = graph.get_state(config)
            if snap and snap.values:
                return TaskStateDTO.model_validate(snap.values)
        except Exception:
            pass
        return fallback

    def _build_graph(self) -> StateGraph:
        """Costruisce il grafo LangGraph con nodi agent, routing e nodi terminali."""
        g = StateGraph(TaskStateDTO)
        for name in (
            "spec",
            "schema",
            "data",
            "query",
            "story",
            "question",
            "critic",
            "hardening",
            "calibration",
            "judge",
        ):
            g.add_node(name, self._make_agent_node(name))
        g.add_node("coverage", self._coverage_node)
        g.add_node("accept", self._accept_node)
        g.add_node("reject", self._reject_node)
        g.set_entry_point("spec")
        g.add_conditional_edges(
            "spec", self._after_generation_step, {"ok": "schema", "scrapped": "reject"}
        )
        g.add_conditional_edges(
            "schema", self._after_generation_step, {"ok": "data", "scrapped": "reject"}
        )
        g.add_conditional_edges(
            "data", self._after_generation_step, {"ok": "query", "scrapped": "reject"}
        )
        g.add_conditional_edges(
            "query", self._after_generation_step, {"ok": "story", "scrapped": "reject"}
        )
        g.add_edge("story", "question")
        g.add_edge("question", "coverage")
        g.add_conditional_edges(
            "coverage",
            self._after_coverage,
            {"ok": "critic", "fail": "story", "scrapped": "reject"},
        )
        g.add_conditional_edges(
            "critic",
            self._route_critic,
            {"harden": "hardening", "calib": "calibration", "scrapped": "reject"},
        )
        g.add_conditional_edges(
            "hardening", self._after_harden, {"loop": "question", "scrapped": "reject"}
        )
        g.add_conditional_edges(
            "calibration",
            self._route_calib,
            {"accept": "accept", "judge": "judge", "harden": "hardening", "reject": "reject"},
        )
        g.add_conditional_edges(
            "judge", self._route_judge, {"regen": "story", "accept": "accept", "reject": "reject"}
        )
        g.add_edge("accept", END)
        g.add_edge("reject", END)
        return g

    def _make_agent_node(self, name: str) -> Callable[..., dict]:
        """Crea una funzione nodo che invoca l'agente corrispondente."""
        agent = self._agents.get(name)
        if agent is None:

            def missing(_state: TaskStateDTO, _config: dict | None = None) -> dict:
                return {
                    "verdict": "scrapped",
                    "last_error": f"Agente '{name}' non registrato.",
                }

            return missing

        def node_fn(state: TaskStateDTO, _config: dict | None = None) -> dict:
            return agent.run(state)

        return node_fn

    def _after_generation_step(self, state: TaskStateDTO) -> str:
        """Instrada dopo uno step di generazione: ok se generato, scrapped se fallito."""
        return "scrapped" if state.verdict == "scrapped" else "ok"

    def _after_coverage(self, state: TaskStateDTO) -> str:
        """Instrada dopo coverage: ok, fail (retry story) o scrapped."""
        if state.verdict == "scrapped":
            return "scrapped"
        if state.last_error:
            bench_cfg = self._config.load_bench()
            max_per_node = bench_cfg.get("retry", {}).get("max_per_node", 3)
            if state.retry_story >= max_per_node:
                return "scrapped"
            return "fail"
        return "ok"

    def _after_harden(self, state: TaskStateDTO) -> str:
        """Instrada dopo hardening: loop a question o scrapped."""
        if state.verdict == "scrapped" or state.last_error:
            return "scrapped"
        return "loop"

    def _route_critic(self, state: TaskStateDTO) -> str:
        """Instrada dopo critic: calib se punteggio alto, hardening altrimenti."""
        if state.verdict == "scrapped":
            return "scrapped"
        if state.critic is None:
            return "scrapped"
        bench_cfg = self._config.load_bench()
        weights = bench_cfg.get("critic", {}).get("weights", {})
        high = bench_cfg.get("thresholds", {}).get("critic_high", 3.5)
        media = weighted_mean(state.critic, weights)
        if media >= high:
            return "calib"
        max_rounds = bench_cfg.get("hardening", {}).get("max_rounds", 3)
        if state.retry_hardening >= max_rounds:
            return "calib"
        return "harden"

    def _route_calib(self, state: TaskStateDTO) -> str:
        """Instrada dopo calibration: accept se passa, judge altrimenti."""
        if state.calibration is None:
            return "reject"
        if state.calibration.passes > 0:
            return "accept"
        return "judge"

    def _route_judge(self, state: TaskStateDTO) -> str:
        """Instrada dopo judge: accept, regen (retry story) o reject."""
        if state.verdict == "scrapped":
            return "reject"
        if state.judge_verdict == "hard":
            return "accept"
        bench_cfg = self._config.load_bench()
        max_regens = bench_cfg.get("judge", {}).get("max_regens", 2)
        if state.judge_regens >= max_regens:
            return "reject"
        return "regen"

    def _coverage_node(self, state: TaskStateDTO) -> dict:
        """Verifica la copertura narrativa delle tabelle e dei valori della gold query."""
        if not state.story or not state.question:
            return {"last_error": "Storia o domanda mancante per la verifica di copertura."}
        if not state.gold_query or not state.spec:
            return {"last_error": "Query gold o specifica mancante per la verifica di copertura."}
        result = self._coverage.validate(
            state.story,
            state.question,
            state.gold_query,
            state.spec,
        )
        if not result.is_valid:
            bench_cfg = self._config.load_bench()
            max_per_node = bench_cfg.get("retry", {}).get("max_per_node", 3)
            if state.retry_story >= max_per_node:
                return {"verdict": "scrapped", "last_error": result.error}
            return {"last_error": result.error}
        return {"last_error": ""}

    def _accept_node(self, state: TaskStateDTO) -> dict:
        """Imposta verdict accepted e calcola il label di difficolta'."""
        label = "hard"
        cal = state.calibration
        if cal and cal.first_pass_attempt == 1:
            label = "easy"
        elif cal and (cal.first_pass_attempt in (2, 3) or cal.passes > 0):
            label = "medium"
        return {"verdict": "accepted", "difficulty_label": label}

    def _reject_node(self, state: TaskStateDTO) -> dict:
        """Imposta verdict rejected, mantenendo scrapped se gia' impostato."""
        if state.verdict == "scrapped":
            return {"verdict": "scrapped"}
        return {"verdict": "rejected"}
