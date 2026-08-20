"""Comando generate per la generazione batch del benchmark.

:author: Riccardo Morabito
"""

from os import _exit as os_exit
from pathlib import Path
from signal import SIGINT, getsignal, signal
from typing import Annotated

from typer import Context, Option, Typer, colors, secho

from bench.adapters.inbound.cli.sigint import (
    _INTERRUPT_EXIT_CODE,
    _INTERRUPT_MSG,
    _TwoStageSigintHandler,
)
from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(help="Generazione batch dei task del benchmark.")


@app.command("generate")
def generate_command(
    ctx: Context,
    limit: Annotated[
        int | None,
        Option(
            "--limit",
            "-l",
            help="Task da generare (default: tutte le categorie del catalogo, senza duplicati).",
        ),
    ] = None,
    category: Annotated[str, Option("--category", "-cat", help="Filtro id categoria.")] = "",
    batch_size: Annotated[int, Option("--batch-size", "-b", help="Worker concorrenti.")] = 1,
    resume: Annotated[
        Path | None,
        Option("--resume", help="Riprende una run esistente dal relativo file JSON."),
    ] = None,
) -> None:
    """Esegue la generazione batch dei task del benchmark in formato JSON unico."""
    bootstrap: ApplicationBootstrap = ctx.obj
    previous_sigint = getsignal(SIGINT)
    _TwoStageSigintHandler.install()
    try:
        runner = bootstrap.task_runner()

        secho("[BENCHMARK] Avvio Generazione Batch Task", fg=colors.CYAN, bold=True)
        secho(f"  Task richiesti (limit): {limit}", fg=colors.WHITE)
        cat_str = category if category else "Tutte (Selezione a giri)"
        secho(f"  Categoria: {cat_str}", fg=colors.WHITE)
        secho(f"  Batch size: {batch_size}", fg=colors.WHITE)
        if resume:
            secho(f"  Resume: {resume}", fg=colors.WHITE)

        summary = runner.run_batch(
            count=limit,
            category=category,
            batch_size=batch_size,
            resume_path=resume,
        )

        secho("\n[RIEPILOGO RUN]", fg=colors.CYAN, bold=True)
        secho(f"  Run ID: {summary.run_id}", fg=colors.WHITE)
        secho(f"  Directory Output: {summary.output_dir}", fg=colors.WHITE)
        secho(f"  Task Richiesti: {summary.requested_count}", fg=colors.WHITE)
        secho(f"  Task Accettati: {summary.accepted_count}", fg=colors.GREEN, bold=True)
        secho(f"  Task Rigettati: {summary.rejected_count}", fg=colors.WHITE)
        secho(f"  Task Scartati: {summary.scrapped_count}", fg=colors.WHITE)
        secho(f"  Task Falliti: {summary.failed_count}", fg=colors.WHITE)
        secho(
            f"  Categorie Coperte: {summary.categories_covered}/{summary.categories_total}",
            fg=colors.WHITE,
        )
        secho(f"  Durata: {summary.duration_seconds}s", fg=colors.WHITE)

        if summary.accepted_count >= summary.requested_count:
            secho("\n[OK] Generazione completata con successo.", fg=colors.GREEN, bold=True)
        else:
            acc_c = summary.accepted_count
            req_c = summary.requested_count
            msg = f"\n[WARNING] Generazione interrotta: generati {acc_c}/{req_c} task."
            secho(msg, fg=colors.YELLOW, bold=True)
            if summary.missing_categories:
                missing_str = ", ".join(summary.missing_categories)
                secho(f"  Categorie mai completate: {missing_str}", fg=colors.YELLOW)
    except KeyboardInterrupt:
        secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
        bootstrap.close()
        os_exit(_INTERRUPT_EXIT_CODE)
    except Exception as e:
        handle_exception(e)
    finally:
        signal(SIGINT, previous_sigint)
