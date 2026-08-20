"""Comando stats per la generazione di analytics e grafici.

:author: Riccardo Morabito
"""

from typing import Annotated

from typer import Context, Option, Typer, colors, secho

from bench.adapters.inbound.cli.sigint import _INTERRUPT_MSG
from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(help="Generazione di analytics e grafici.")


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
                f"[OK] Analytics e {res.plots_count} grafici generati con successo per "
                f"{res.total_tasks} task (Run ID: {res.run_id})."
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
