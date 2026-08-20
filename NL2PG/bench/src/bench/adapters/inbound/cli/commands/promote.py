"""Comando promote per la promozione dei task accettati.

:author: Riccardo Morabito
"""

from typer import Context, Typer, colors, secho

from bench.adapters.inbound.cli.sigint import _INTERRUPT_MSG
from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(help="Promozione dei campioni in examples/.")


@app.command("promote")
def promote_command(ctx: Context) -> None:
    """Promuove i task accettati da output/ in examples/<categoria>/<ruolo>/."""
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
