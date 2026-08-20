"""Adattatore Inbound CLI per la gestione ed esecuzione del benchmark.

:author: Riccardo Morabito
"""

from os import environ

environ.setdefault("HF_HUB_OFFLINE", "1")

from typer import Context, Typer

from bench.application.bootstrap import ApplicationBootstrap

from .commands.check import app as check_app
from .commands.cleanup import app as cleanup_app
from .commands.generate import app as generate_app
from .commands.promote import app as promote_app
from .commands.stats import app as stats_app

app = Typer(
    name="bench",
    help="Bench - Generatore di dataset sintetici SQL e Natural Language.",
    add_completion=False,
)


@app.callback()
def main_callback(ctx: Context) -> None:
    """Inizializza la Composition Root ed inserisce il teardown nel ciclo di vita Typer."""
    bootstrap = ApplicationBootstrap()
    ctx.obj = bootstrap
    ctx.call_on_close(bootstrap.close)


app.add_typer(generate_app)
app.add_typer(check_app)
app.add_typer(promote_app)
app.add_typer(cleanup_app)
app.add_typer(stats_app)
