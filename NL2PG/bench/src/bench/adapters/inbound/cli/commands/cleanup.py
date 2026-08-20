"""Comando cleanup per la pulizia degli schemi temporanei.

:author: Riccardo Morabito
"""

from typer import Context, Typer, colors, secho

from bench.adapters.inbound.cli.sigint import _INTERRUPT_MSG
from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(help="Pulizia degli schemi temporanei sandbox.")


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
