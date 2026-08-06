"""Adattatore Inbound CLI per la gestione ed esecuzione del benchmark.

:author: Riccardo Morabito
"""

from json import dumps, loads
from os import _exit as os_exit
from typing import Annotated

from typer import Option, Typer, colors, secho

from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception
from bench.domain.models.nlp import JudgeDTO

app = Typer(
    name="bench",
    help="Bench - Generatore di dataset sintetici SQL e Natural Language.",
    add_completion=False,
)


@app.command("generate")
def generate_command(
    count: Annotated[int, Option("--count", "-c", help="Numero di task da generare.")] = 10,
    category: Annotated[str, Option("--category", "-cat", help="Filtro id categoria.")] = "",
    batch_size: Annotated[int, Option("--batch-size", "-b", help="Worker concorrenti.")] = 1,
) -> None:
    """Esegue la generazione batch dei task del benchmark in formato JSON unico."""
    bootstrap = ApplicationBootstrap()
    exit_code = 0
    try:
        runner = bootstrap.task_runner()

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
        exit_code = 1
        handle_exception(e)
    finally:
        bootstrap.close()
        os_exit(exit_code)


@app.command("check-providers")
def check_providers_command() -> None:
    """Esegue una verifica di connettività e risposta sui provider LLM configurati."""
    bootstrap = ApplicationBootstrap()
    exit_code = 0
    try:
        secho("[INFO] Verifica connettivita' provider LLM in corso...", fg=colors.CYAN)

        res = bootstrap.llm.call_model(
            role="default",
            prompt='Rispondi esclusivamente con un oggetto JSON: {"verdict": "hard"}',
            schema=JudgeDTO,
        )
        msg = f"[OK] Connessione LLM riuscita tramite il modello: {res.model_used}"
        secho(msg, fg=colors.GREEN, bold=True)
    except Exception as e:
        exit_code = 1
        secho(f"[ERRORE] Verifica provider LLM fallita: {e}", fg=colors.RED, bold=True)
        handle_exception(e)
    finally:
        bootstrap.close()
        os_exit(exit_code)


@app.command("check")
def check_command() -> None:
    """Verifica l'integrità dei file di configurazione e calcola gli hash di esecuzione."""
    bootstrap = ApplicationBootstrap()
    exit_code = 0
    try:
        cfg = bootstrap.config
        bench_cfg = cfg.load_bench()
        providers_cfg = cfg.load_providers()
        categories = cfg.load_categories()

        cfg_hash = cfg.config_hash(bench_cfg)
        cat_hash = cfg.config_hash({"categories": list(categories.keys())})

        secho("[INFO] Stato Configurazioni Benchmark:", fg=colors.CYAN, bold=True)
        secho("  bench.toml: OK (Caricato)", fg=colors.WHITE)
        models_count = len(providers_cfg.get("models", {}))
        secho(f"  providers.json: OK ({models_count} modelli)", fg=colors.WHITE)
        secho(f"  categories.json: OK ({len(categories)} categorie)", fg=colors.WHITE)
        secho(f"  Config Hash: {cfg_hash}", fg=colors.WHITE)
        secho(f"  Categories Hash: {cat_hash}", fg=colors.WHITE)

        secho("[OK] Controllo configurazioni completato con successo.", fg=colors.GREEN, bold=True)
    except Exception as e:
        exit_code = 1
        handle_exception(e)
    finally:
        bootstrap.close()
        os_exit(exit_code)


@app.command("promote")
def promote_command() -> None:
    """Promuove i task accettati da output/ verso la cartella esempi examples/<categoria>/."""
    bootstrap = ApplicationBootstrap()
    exit_code = 0
    try:
        base_dir = bootstrap.config.get_config_dir().parent
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
        exit_code = 1
        handle_exception(e)
    finally:
        bootstrap.close()
        os_exit(exit_code)


@app.command("cleanup")
def cleanup_command() -> None:
    """Pulisce gli schemi temporanei orfani (task_*) nel database sandbox PostgreSQL."""
    bootstrap = ApplicationBootstrap()
    exit_code = 0
    try:
        secho("[INFO] Avvio pulizia schemi temporanei sandbox PostgreSQL...", fg=colors.CYAN)

        pg = bootstrap.pg_client
        removed_schemas = []
        with pg.get_sandbox_connection(autocommit=True) as conn:
            query = (
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'task_%'"
            )
            _, rows = pg.execute_query(conn, query)
            for (schema_name,) in rows:
                pg.execute_identifier(conn, "DROP SCHEMA IF EXISTS {} CASCADE", schema_name)
                removed_schemas.append(schema_name)

        msg = f"[OK] Pulizia completata con successo: {len(removed_schemas)} schemi rimossi."
        secho(msg, fg=colors.GREEN, bold=True)
    except Exception as e:
        exit_code = 1
        handle_exception(e)
    finally:
        bootstrap.close()
        os_exit(exit_code)
