"""Adattatore Inbound CLI per la gestione ed esecuzione del benchmark.

:author: Riccardo Morabito
"""

from json import dumps, loads
from pathlib import Path
from sys import exit as sys_exit
from typing import Annotated

from typer import Option, Typer, colors, secho

from bench.adapters.outbound.config import ConfigAdapter
from bench.adapters.outbound.llm import LLMClientAdapter
from bench.adapters.outbound.logging import LoggingAdapter
from bench.adapters.outbound.postgres import (
    MetaRepositoryAdapter,
    PostgresClientAdapter,
    PostgresSandboxAdapter,
)
from bench.adapters.outbound.prompts import PromptAdapter
from bench.application.agents import (
    CalibrationAgent,
    CriticAgent,
    DataAgent,
    HardeningAgent,
    JudgeAgent,
    QueryAgent,
    QuestionAgent,
    SchemaAgent,
    SpecAgent,
    StoryAgent,
)
from bench.application.orchestrator import Orchestrator
from bench.application.serializer import BenchmarkSerializer
from bench.application.services import TaskRunner
from bench.domain.exceptions import handle_exception, install_global_handler
from bench.domain.models.nlp import JudgeDTO

app = Typer(
    name="bench",
    help="Bench - Generatore di dataset sintetici SQL e Natural Language.",
    add_completion=False,
)


def _init_components(
    config_dir: Path | None = None,
) -> tuple[ConfigAdapter, PostgresClientAdapter, LLMClientAdapter, TaskRunner]:
    """Inizializza il logging, gestore eccezioni e tutte le dipendenze della pipeline."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    cfg_dir = config_dir or (base_dir / "config")

    log_adapter = LoggingAdapter(level="DEBUG")
    log_adapter.configure()
    install_global_handler()

    config_adapter = ConfigAdapter(cfg_dir)
    providers_cfg = config_adapter.load_providers()
    llm_adapter = LLMClientAdapter(providers_cfg)

    pg_client = PostgresClientAdapter(config=config_adapter.load_bench().get("run", {}))
    sandbox_adapter = PostgresSandboxAdapter(pg_client)
    meta_repo = MetaRepositoryAdapter(pg_client)
    prompt_adapter = PromptAdapter(base_dir / "prompts")

    agents = {
        "spec": SpecAgent(llm_adapter, prompt_adapter, config_adapter),
        "schema": SchemaAgent(
            llm_adapter, prompt_adapter, config_adapter, sandbox_adapter
        ),
        "data": DataAgent(
            llm_adapter, prompt_adapter, config_adapter, sandbox_adapter
        ),
        "query": QueryAgent(
            llm_adapter, prompt_adapter, config_adapter, sandbox_adapter, pg_client
        ),
        "story": StoryAgent(llm_adapter, prompt_adapter, config_adapter),
        "question": QuestionAgent(llm_adapter, prompt_adapter, config_adapter),
        "critic": CriticAgent(llm_adapter, prompt_adapter, config_adapter),
        "hardening": HardeningAgent(llm_adapter, prompt_adapter, config_adapter),
        "calibration": CalibrationAgent(
            llm_adapter, prompt_adapter, config_adapter, sandbox_adapter
        ),
        "judge": JudgeAgent(llm_adapter, prompt_adapter, config_adapter),
    }

    orchestrator = Orchestrator(sandbox_adapter, config_adapter, meta_repo, agents)
    serializer = BenchmarkSerializer()
    runner = TaskRunner(orchestrator, meta_repo, serializer, config_adapter)

    return config_adapter, pg_client, llm_adapter, runner


@app.command("generate")
def generate_command(
    count: Annotated[int, Option("--count", "-c", help="Numero di task da generare.")] = 10,
    category: Annotated[str, Option("--category", "-cat", help="Filtro id categoria.")] = "",
    batch_size: Annotated[int, Option("--batch-size", "-b", help="Worker concorrenti.")] = 1,
) -> None:
    """Esegue la generazione batch dei task del benchmark in formato JSON unico."""
    try:
        _, _, _, runner = _init_components()

        secho("[BENCHMARK] Avvio Generazione Batch Task", fg=colors.CYAN, bold=True)
        secho(f"  Task richiesti: {count}", fg=colors.WHITE)
        cat_str = category if category else "Tutte (Selezione casuale)"
        secho(f"  Categoria: {cat_str}", fg=colors.WHITE)
        secho(f"  Batch size: {batch_size}", fg=colors.WHITE)

        summary = runner.run_batch(count=count, category=category, batch_size=batch_size)

        secho("\n[RIEPILOGO RUN]", fg=colors.CYAN, bold=True)
        secho(f"  Run ID: {summary.run_id}", fg=colors.WHITE)
        secho(f"  Directory Output: {summary.output_dir}", fg=colors.WHITE)
        secho(f"  Task Richiesti: {summary.requested_count}", fg=colors.WHITE)
        secho(f"  Task Accettati: {summary.accepted_count}", fg=colors.GREEN, bold=True)
        secho(f"  Task Rigettati: {summary.rejected_count}", fg=colors.WHITE)
        secho(f"  Task Scartati: {summary.scrapped_count}", fg=colors.WHITE)
        secho(f"  Task Falliti: {summary.failed_count}", fg=colors.WHITE)
        secho(f"  Durata: {summary.duration_seconds}s", fg=colors.WHITE)

        if summary.accepted_count >= summary.requested_count:
            secho("\n[OK] Generazione completata con successo.", fg=colors.GREEN, bold=True)
        else:
            acc_c = summary.accepted_count
            req_c = summary.requested_count
            msg = f"\n[WARNING] Generazione interrotta: generati {acc_c}/{req_c} task."
            secho(msg, fg=colors.YELLOW, bold=True)
    except Exception as e:
        handle_exception(e)
        sys_exit(1)


@app.command("check-providers")
def check_providers_command() -> None:
    """Esegue una verifica di connettività e risposta sui provider LLM configurati."""
    try:
        _, _, llm_adapter, _ = _init_components()
        secho("[INFO] Verifica connettivita' provider LLM in corso...", fg=colors.CYAN)

        res = llm_adapter.call_model(
            role="default",
            prompt='Rispondi esclusivamente con un oggetto JSON: {"verdict": "hard"}',
            schema=JudgeDTO,
        )
        msg = f"[OK] Connessione LLM riuscita tramite il modello: {res.model_used}"
        secho(msg, fg=colors.GREEN, bold=True)
    except Exception as e:
        secho(f"[ERRORE] Verifica provider LLM fallita: {e}", fg=colors.RED, bold=True)
        handle_exception(e)
        sys_exit(1)


@app.command("check")
def check_command() -> None:
    """Verifica l'integrità dei file di configurazione e calcola gli hash di esecuzione."""
    try:
        config_adapter, _, _, _ = _init_components()
        bench_cfg = config_adapter.load_bench()
        providers_cfg = config_adapter.load_providers()
        categories = config_adapter.load_categories()

        cfg_hash = config_adapter.config_hash(bench_cfg)
        cat_hash = config_adapter.config_hash({"categories": list(categories.keys())})

        secho("[INFO] Stato Configurazioni Benchmark:", fg=colors.CYAN, bold=True)
        secho("  bench.toml: OK (Caricato)", fg=colors.WHITE)
        models_count = len(providers_cfg.get("models", {}))
        secho(f"  providers.json: OK ({models_count} modelli)", fg=colors.WHITE)
        secho(f"  categories.json: OK ({len(categories)} categorie)", fg=colors.WHITE)
        secho(f"  Config Hash: {cfg_hash}", fg=colors.WHITE)
        secho(f"  Categories Hash: {cat_hash}", fg=colors.WHITE)

        secho("[OK] Controllo configurazioni completato con successo.", fg=colors.GREEN, bold=True)
    except Exception as e:
        handle_exception(e)
        sys_exit(1)


@app.command("promote")
def promote_command() -> None:
    """Promuove i task accettati da output/ verso la cartella esempi examples/<categoria>/."""
    try:
        config_adapter, _, _, _ = _init_components()
        base_dir = config_adapter.get_config_dir().parent
        out_dir = base_dir / "output"
        examples_dir = base_dir / "examples"

        if not out_dir.exists():
            secho("[INFO] Nessuna directory output/ trovata per la promozione.", fg=colors.YELLOW)
            return

        promoted_count = 0
        for sample_file in sorted(out_dir.rglob("benchmark_samples.json")):
            try:
                doc = loads(sample_file.read_text(encoding="utf-8"))
                for task in doc.get("tasks", []):
                    cat = task.get("category", "unknown")
                    cat_dir = examples_dir / cat
                    cat_dir.mkdir(parents=True, exist_ok=True)

                    task_file = cat_dir / f"{task['task_id']}.json"
                    task_file.write_text(
                        dumps(task, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8",
                    )
                    promoted_count += 1
            except Exception as e:
                err_msg = f"[WARNING] Errore promozione file {sample_file.name}: {e}"
                secho(err_msg, fg=colors.YELLOW)

        msg = f"[OK] Promozione completata: {promoted_count} campioni promossi in 'examples/'."
        secho(msg, fg=colors.GREEN, bold=True)
    except Exception as e:
        handle_exception(e)
        sys_exit(1)


@app.command("cleanup")
def cleanup_command() -> None:
    """Pulisce gli schemi temporanei orfani (task_*) nel database sandbox PostgreSQL."""
    try:
        _, pg_client, _, _ = _init_components()
        secho("[INFO] Avvio pulizia schemi temporanei sandbox PostgreSQL...", fg=colors.CYAN)

        removed_schemas = []
        with pg_client.get_sandbox_connection(autocommit=True) as conn:
            query = (
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'task_%'"
            )
            _, rows = pg_client.execute_query(conn, query)
            for (schema_name,) in rows:
                pg_client.execute_identifier(conn, "DROP SCHEMA IF EXISTS {} CASCADE", schema_name)
                removed_schemas.append(schema_name)

        msg = f"[OK] Pulizia completata con successo: {len(removed_schemas)} schemi rimossi."
        secho(msg, fg=colors.GREEN, bold=True)
    except Exception as e:
        handle_exception(e)
        sys_exit(1)
