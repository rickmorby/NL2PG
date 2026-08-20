"""Comando check per la diagnosi di configurazioni e provider.

:author: Riccardo Morabito
"""

from typing import Annotated

from typer import Context, Option, Typer, colors, secho

from bench.adapters.inbound.cli.presenter import _CLIConsolePresenter
from bench.adapters.inbound.cli.sigint import _INTERRUPT_MSG
from bench.application.bootstrap import ApplicationBootstrap
from bench.domain.exceptions import handle_exception

app = Typer(help="Diagnosi di configurazioni e provider.")


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
        bool, Option("--all", "-a", help="Diagnosi completa (Config + Provider + Modelli).")
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
            _CLIConsolePresenter.print_provider_tree(report, do_models=do_models)
    except KeyboardInterrupt:
        secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
    except Exception as e:
        secho(f"[ERRORE] Diagnosi fallita: {e}", fg=colors.RED, bold=True)
        handle_exception(e)
