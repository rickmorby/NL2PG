"""Adattatore Inbound CLI per la gestione ed esecuzione del benchmark.

:author: Riccardo Morabito
"""

from sys import exit as sys_exit
from typing import Annotated

from typer import Option, Typer, colors, secho

from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(
    name="bench",
    help="Bench - Generatore di dataset sintetici SQL e Natural Language.",
    add_completion=False,
)

_INTERRUPT_MSG = "\n[WARNING] Interruzione da tastiera (Ctrl+C). Chiusura in corso..."


@app.command("generate")
def generate_command(
    count: Annotated[int, Option("--count", "-c", help="Numero di task da generare.")] = 10,
    category: Annotated[str, Option("--category", "-cat", help="Filtro id categoria.")] = "",
    batch_size: Annotated[int, Option("--batch-size", "-b", help="Worker concorrenti.")] = 1,
) -> None:
    """Esegue la generazione batch dei task del benchmark in formato JSON unico."""
    exit_code = 0
    with ApplicationBootstrap() as bootstrap:
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
        except KeyboardInterrupt:
            secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
            exit_code = 130
        except Exception as e:
            exit_code = 1
            handle_exception(e)
    sys_exit(exit_code)


@app.command("check-providers")
def check_providers_command() -> None:
    """Esegue una verifica di connettività e risposta sui provider LLM configurati."""
    exit_code = 0
    with ApplicationBootstrap() as bootstrap:
        try:
            secho("[INFO] Verifica connettivita' provider LLM in corso...", fg=colors.CYAN)
            checker = bootstrap.system_checker()
            res = checker.check_llm_providers()

            if res.success:
                msg = f"[OK] Connessione LLM riuscita tramite il modello: {res.model_used}"
                secho(msg, fg=colors.GREEN, bold=True)
            else:
                msg_err = f"[ERRORE] Verifica provider LLM fallita: {res.error}"
                secho(msg_err, fg=colors.RED, bold=True)
                exit_code = 1
        except KeyboardInterrupt:
            secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
            exit_code = 130
        except Exception as e:
            exit_code = 1
            secho(f"[ERRORE] Invocazione fallita: {e}", fg=colors.RED, bold=True)
            handle_exception(e)
    sys_exit(exit_code)


@app.command("check")
def check_command() -> None:
    """Verifica l'integrità dei file di configurazione e calcola gli hash di esecuzione."""
    exit_code = 0
    with ApplicationBootstrap() as bootstrap:
        try:
            checker = bootstrap.system_checker()
            res = checker.check_configurations()

            secho("[INFO] Stato Configurazioni Benchmark:", fg=colors.CYAN, bold=True)
            secho("  bench.toml: OK (Caricato)", fg=colors.WHITE)
            secho(f"  providers.json: OK ({res.models_count} modelli)", fg=colors.WHITE)
            secho(f"  categories.json: OK ({res.categories_count} categorie)", fg=colors.WHITE)
            secho(f"  Config Hash: {res.config_hash}", fg=colors.WHITE)
            secho(f"  Categories Hash: {res.categories_hash}", fg=colors.WHITE)

            msg_ok = "[OK] Controllo configurazioni completato con successo."
            secho(msg_ok, fg=colors.GREEN, bold=True)
        except KeyboardInterrupt:
            secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
            exit_code = 130
        except Exception as e:
            exit_code = 1
            handle_exception(e)
    sys_exit(exit_code)


@app.command("promote")
def promote_command() -> None:
    """Promuove i task accettati da output/ verso la cartella esempi examples/<categoria>/."""
    exit_code = 0
    with ApplicationBootstrap() as bootstrap:
        try:
            base_dir = bootstrap.base_dir
            out_dir = base_dir / "output"
            examples_dir = base_dir / "examples"

            promoter = bootstrap.task_promoter()
            promoted_count = promoter.promote_accepted_tasks(out_dir, examples_dir)

            if promoted_count > 0:
                msg = f"[OK] Promozione completata: {promoted_count} campioni in 'examples/'."
                secho(msg, fg=colors.GREEN, bold=True)
            else:
                secho("[INFO] Nessun nuovo campione trovato da promuovere.", fg=colors.YELLOW)
        except KeyboardInterrupt:
            secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
            exit_code = 130
        except Exception as e:
            exit_code = 1
            handle_exception(e)
    sys_exit(exit_code)


@app.command("cleanup")
def cleanup_command() -> None:
    """Pulisce gli schemi temporanei orfani (task_*) nel database sandbox PostgreSQL."""
    exit_code = 0
    with ApplicationBootstrap() as bootstrap:
        try:
            secho("[INFO] Avvio pulizia schemi temporanei sandbox PostgreSQL...", fg=colors.CYAN)
            cleaner = bootstrap.database_cleaner()
            removed_schemas = cleaner.cleanup_sandbox_schemas()

            msg = f"[OK] Pulizia completata con successo: {len(removed_schemas)} schemi rimossi."
            secho(msg, fg=colors.GREEN, bold=True)
        except KeyboardInterrupt:
            secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
            exit_code = 130
        except Exception as e:
            exit_code = 1
            handle_exception(e)
    sys_exit(exit_code)


@app.command("stats")
def stats_command(
    run: Annotated[str, Option("--run", "-r", help="ID o nome opzionale della run.")] = "",
) -> None:
    """Genera le metriche analytics.json ed i 12 grafici scientifici PNG per la run."""
    exit_code = 0
    with ApplicationBootstrap() as bootstrap:
        try:
            secho("[INFO] Avvio generazione analytics e grafici scientifici...", fg=colors.CYAN)
            analytics_svc = bootstrap.analytics()
            out_dir = bootstrap.base_dir / "output"
            target = out_dir / "benchmarks" / run if run else out_dir
            res = analytics_svc.generate_analytics(target)

            if res.total_tasks > 0:
                msg = (
                    f"[OK] Analytics e 12 grafici generati con successo per {res.total_tasks} task "
                    f"(Run ID: {res.run_id})."
                )
                secho(msg, fg=colors.GREEN, bold=True)
            else:
                msg_warn = "[WARNING] Nessun task analizzabile trovato nel percorso specificato."
                secho(msg_warn, fg=colors.YELLOW)
        except KeyboardInterrupt:
            secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
            exit_code = 130
        except Exception as e:
            exit_code = 1
            handle_exception(e)
    sys_exit(exit_code)
