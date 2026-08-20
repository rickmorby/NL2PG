"""Presenter CLI per la visualizzazione Rich dei provider.

:author: Riccardo Morabito
"""

from typing import Any

from rich.console import Console
from rich.tree import Tree
from typer import colors, secho


class _CLIConsolePresenter:
    """Presenter dedicato per la formattazione e visualizzazione Rich su console."""

    @staticmethod
    def print_provider_tree(report: Any, *, do_models: bool) -> None:
        """Stampa l'albero gerarchico dei provider e dei modelli su console con Rich."""
        console = Console()
        for p in report.providers:
            if p.is_reachable:
                p_title = (
                    f"[bold green][OK] Provider {p.provider_name} ({p.base_url}): "
                    f"RAGGIUNGIBILE [{len(p.models)} modelli][/bold green]"
                )
            else:
                p_title = (
                    f"[bold red][ERRORE] Provider {p.provider_name} ({p.base_url}): "
                    f"NON RAGGIUNGIBILE -> {p.error_message}[/bold red]"
                )

            tree = Tree(p_title)
            if do_models:
                for m in p.models:
                    roles_str = f"[dim][Ruoli: {', '.join(m.roles)}][/dim]" if m.roles else ""
                    if m.is_healthy:
                        tree.add(f"[green]{m.target_model} {roles_str} -> DISPONIBILE [OK][/green]")
                    else:
                        msg_err_str = (
                            f"[red]{m.target_model} {roles_str} -> "
                            f"NON DISPONIBILE ({m.error_message})[/red]"
                        )
                        tree.add(msg_err_str)
            console.print(tree)
            console.print("")

        msg_summary = (
            f"[RIEPILOGO DIAGNOSI] Provider raggiungibili: "
            f"{report.reachable_providers}/{report.total_providers}"
        )
        if do_models:
            msg_summary += (
                f" | Modelli fisici operativi: {report.healthy_models}/{report.total_models}"
            )
        secho(msg_summary, fg=colors.CYAN, bold=True)
