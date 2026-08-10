"""Adattatore Inbound CLI per la gestione ed esecuzione del benchmark.

:author: Riccardo Morabito
"""

from typing import Annotated

from typer import Context, Option, Typer, colors, secho

from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(
    name="bench",
    help="Bench - Generatore di dataset sintetici SQL e Natural Language.",
    add_completion=False,
)

_INTERRUPT_MSG = "\n[WARNING] Interruzione da tastiera (Ctrl+C). Chiusura in corso..."


@app.callback()
def main_callback(ctx: Context) -> None:
    """Inizializza la Composition Root ed inserisce il teardown nel ciclo di vita Typer."""
    bootstrap = ApplicationBootstrap()
    ctx.obj = bootstrap
    ctx.call_on_close(bootstrap.close)


@app.command("generate")
def generate_command(
    ctx: Context,
    count: Annotated[int, Option("--count", "-c", help="Numero di task da generare.")] = 10,
    category: Annotated[str, Option("--category", "-cat", help="Filtro id categoria.")] = "",
    batch_size: Annotated[int, Option("--batch-size", "-b", help="Worker concorrenti.")] = 1,
) -> None:
    """Esegue la generazione batch dei task del benchmark in formato JSON unico."""
    bootstrap: ApplicationBootstrap = ctx.obj
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
        secho(
            _INTERRUPT_MSG,
            fg=colors.YELLOW,
            bold=True,
        )
    except Exception as e:
        handle_exception(e)


@app.command("check")
def check_command(
    ctx: Context,
    providers_only: Annotated[
        bool, Option("--providers", "-p", help="Verifica la connettività dei provider.")
    ] = False,
    models_check: Annotated[
        bool, Option("--models", "-m", help="Verifica provider e modelli fisici.")
    ] = False,
    config_only: Annotated[
        bool, Option("--config", "-cfg", help="Verifica l'integrità delle configurazioni.")
    ] = False,
    all_check: Annotated[
        bool, Option("--all", "-a", help="Diagnosi completa 360° (Config + Provider + Modelli).")
    ] = False,
) -> None:
    """Diagnosi unificata di configurazioni, connettività provider e modelli LLM."""
    bootstrap: ApplicationBootstrap = ctx.obj
    try:
        checker = bootstrap.system_checker()
        do_config = config_only or all_check or (not providers_only and not models_check)
        do_providers = providers_only or models_check or all_check
        do_models = models_check or all_check

        if do_config:
            res = checker.check_configurations()
            secho("[INFO] Stato Configurazioni Benchmark:", fg=colors.CYAN, bold=True)
            secho("  bench.toml: OK (Caricato)", fg=colors.WHITE)
            secho(f"  providers.json: OK ({res.models_count} modelli)", fg=colors.WHITE)
            secho(f"  categories.json: OK ({res.categories_count} categorie)", fg=colors.WHITE)
            secho(f"  Config Hash: {res.config_hash}", fg=colors.WHITE)
            secho(f"  Categories Hash: {res.categories_hash}\n", fg=colors.WHITE)

        if do_providers:
            msg_start = "[INFO] Avvio diagnosi connettività provider ed LLM...\n"
            secho(msg_start, fg=colors.CYAN, bold=True)
            report = checker.check_llm_providers(check_models=do_models)

            for p in report.providers:
                if p.is_reachable:
                    p_msg = (
                        f"[OK] Provider {p.provider_name} ({p.base_url}): "
                        f"RAGGIUNGIBILE [{len(p.models)} modelli]"
                    )
                    secho(p_msg, fg=colors.GREEN, bold=True)
                else:
                    p_msg = (
                        f"[ERRORE] Provider {p.provider_name} ({p.base_url}): "
                        f"NON RAGGIUNGIBILE -> {p.error_message}"
                    )
                    secho(p_msg, fg=colors.RED, bold=True)

                if do_models:
                    total_m = len(p.models)
                    for idx, m in enumerate(p.models):
                        connector = "  └── " if idx == total_m - 1 else "  ├── "
                        roles_str = f"[Ruoli: {', '.join(m.roles)}]" if m.roles else ""
                        status_str = f"{connector}{m.target_model} {roles_str} -> "
                        if m.is_healthy:
                            secho(f"{status_str}DISPONIBILE [OK]", fg=colors.GREEN)
                        else:
                            secho(
                                f"{status_str}NON DISPONIBILE ({m.error_message})",
                                fg=colors.RED,
                            )
                secho("")

            msg_summary = (
                f"[RIEPILOGO DIAGNOSI] Provider raggiungibili: "
                f"{report.reachable_providers}/{report.total_providers}"
            )
            if do_models:
                msg_summary += (
                    f" | Modelli fisici operativi: "
                    f"{report.healthy_models}/{report.total_models}"
                )
            secho(msg_summary, fg=colors.CYAN, bold=True)
    except KeyboardInterrupt:
        secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
    except Exception as e:
        secho(f"[ERRORE] Diagnosi fallita: {e}", fg=colors.RED, bold=True)
        handle_exception(e)


@app.command("check-providers")
def check_providers_command(ctx: Context) -> None:
    """Alias di 'bench check --models' per la verifica di provider e modelli LLM."""
    check_command(ctx, models_check=True)


@app.command("promote")
def promote_command(ctx: Context) -> None:
    """Promuove i task accettati da output/ verso la cartella esempi examples/<categoria>/."""
    bootstrap: ApplicationBootstrap = ctx.obj
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
        secho(
            _INTERRUPT_MSG,
            fg=colors.YELLOW,
            bold=True,
        )
    except Exception as e:
        handle_exception(e)


@app.command("cleanup")
def cleanup_command(ctx: Context) -> None:
    """Pulisce gli schemi temporanei orfani (task_*) nel database sandbox PostgreSQL."""
    bootstrap: ApplicationBootstrap = ctx.obj
    try:
        secho("[INFO] Avvio pulizia schemi temporanei sandbox PostgreSQL...", fg=colors.CYAN)
        cleaner = bootstrap.database_cleaner()
        removed_schemas = cleaner.cleanup_sandbox_schemas()

        msg = f"[OK] Pulizia completata con successo: {len(removed_schemas)} schemi rimossi."
        secho(msg, fg=colors.GREEN, bold=True)
    except KeyboardInterrupt:
        secho(
            _INTERRUPT_MSG,
            fg=colors.YELLOW,
            bold=True,
        )
    except Exception as e:
        handle_exception(e)


@app.command("stats")
def stats_command(
    ctx: Context,
    run: Annotated[str, Option("--run", "-r", help="ID o nome opzionale della run.")] = "",
) -> None:
    """Genera le metriche analytics.json ed i 12 grafici scientifici PNG per la run."""
    bootstrap: ApplicationBootstrap = ctx.obj
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
        secho(
            _INTERRUPT_MSG,
            fg=colors.YELLOW,
            bold=True,
        )
    except Exception as e:
        handle_exception(e)
