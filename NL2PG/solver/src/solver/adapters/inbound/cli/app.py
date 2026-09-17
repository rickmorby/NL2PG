"""Adattatore Inbound CLI Typer / Rich per la gestione ed esecuzione del solver.

:author: Riccardo Morabito
"""

from os import _exit as os_exit
from pathlib import Path
from signal import SIGINT, getsignal, signal
from typing import Annotated

from typer import Context, Option, Typer, colors, secho

from solver.application.bootstrap import ApplicationBootstrap
from solver.domain.exceptions import handle_exception
from solver.domain.models.solver import SolverRunDTO

app = Typer(
    name="solver",
    help="Solver - Valutatore e Risolutore Scientifico del Benchmark per SQL e Datalog.",
    add_completion=False,
)

_INTERRUPT_MSG = "\n[WARNING] Interruzione da tastiera (Ctrl+C). Chiusura in corso..."
_INTERRUPT_LIMIT = 2
_INTERRUPT_EXIT_CODE = 130


class _TwoStageSigintHandler:
    """Gestore del segnale SIGINT a due stadi (graceful e forzato)."""

    def __init__(self) -> None:
        self._count = 0

    def __call__(self, _signum: int, _frame: object) -> None:
        self._count += 1
        if self._count >= _INTERRUPT_LIMIT:
            secho(
                "[WARNING] Seconda interruzione: uscita forzata immediata.",
                fg=colors.YELLOW,
            )
            os_exit(_INTERRUPT_EXIT_CODE)
        raise KeyboardInterrupt

    @staticmethod
    def install() -> None:
        """Installa SIGINT a 2 stadi: 1. KeyboardInterrupt (graceful), 2. os_exit(130)."""
        signal(SIGINT, _TwoStageSigintHandler())


class _SolverCLISummaryPresenter:
    """Presenter dedicato per la formattazione e visualizzazione del riepilogo su console."""

    @staticmethod
    def print_summary(run_dto: SolverRunDTO, output_dir: Path) -> None:
        """Stampa il riepilogo finale della run di risoluzione con metriche scientifiche."""
        s = run_dto.summary
        secho("\n[RIEPILOGO SOLVER RUN]", fg=colors.CYAN, bold=True)
        secho(f"  Run ID: {run_dto.run_id}", fg=colors.WHITE)
        secho(f"  Task Valutati: {s.tasks_evaluated}/{s.total_tasks}", fg=colors.WHITE)
        secho(
            f"  Accuracy SQL (RAG + Sandbox): {s.pass_rate_sql_rag_sandbox_gold * 100:.1f}%",
            fg=colors.GREEN,
            bold=True,
        )
        secho(
            f"  Accuracy SQL (Zero-Shot): {s.pass_rate_sql_zero_shot_gold * 100:.1f}%",
            fg=colors.GREEN,
            bold=True,
        )
        secho(
            f"  Accuracy Datalog (RAG + Clingo): {s.pass_rate_datalog_rag_clingo_gold * 100:.1f}%",
            fg=colors.GREEN,
            bold=True,
        )
        msg_trans = (
            f"  Accuracy SQL->Datalog (Transpiled): "
            f"{s.pass_rate_sql_to_datalog_transpiled_gold * 100:.1f}%"
        )
        secho(msg_trans, fg=colors.GREEN, bold=True)
        secho(
            f"  Schema Accuracy (SA): {s.schema_accuracy * 100:.1f}% "
            f"(F1 medio: {s.schema_f1_mean * 100:.1f}%)",
            fg=colors.GREEN,
            bold=True,
        )
        secho(
            f"  Schema Gap (G_schema): {s.schema_gap * 100:.1f}%",
            fg=colors.CYAN,
            bold=True,
        )
        secho(f"  Tasso Risposte One-Shot: {s.one_shot_rate * 100:.1f}%", fg=colors.WHITE)
        secho(f"  Tasso Uso Tool: {s.tool_usage_rate * 100:.1f}%", fg=colors.WHITE)
        secho(f"  Durata: {s.duration_seconds}s", fg=colors.WHITE)
        saved_file = output_dir / f"solver_{run_dto.run_id}.json"
        secho(f"\n[OK] Risultati salvati in: {saved_file}", fg=colors.GREEN, bold=True)


@app.callback()
def main_callback(ctx: Context) -> None:
    """Inizializza la Composition Root ed inserisce il teardown nel ciclo di vita Typer."""
    bootstrap = ApplicationBootstrap()
    ctx.obj = bootstrap
    ctx.call_on_close(bootstrap.close)


@app.command("solve")
def solve_command(
    ctx: Context,
    benchmark: Annotated[
        str, Option("--benchmark", "-b", help="Percorso del file JSON del benchmark.")
    ] = "",
    recipes: Annotated[
        str,
        Option(
            "--recipes",
            "-r",
            help="Elenco ricette (es. text_to_sql_rag_sandbox,text_to_sql_zero_shot).",
        ),
    ] = "",
    limit: Annotated[
        int,
        Option(
            "--limit",
            "-l",
            help="Task da valutare (default: 0, copertura completa del benchmark).",
        ),
    ] = 0,
    model: Annotated[
        str, Option("--model", "-m", help="Nome o ruolo del modello LLM da utilizzare.")
    ] = "default",
    batch_size: Annotated[
        int, Option("--batch-size", "-bs", help="Numero di worker concorrenti.")
    ] = 1,
) -> None:
    """Esegue la risoluzione del benchmark sulle ricette scientifiche specificate."""
    bootstrap: ApplicationBootstrap = ctx.obj
    previous_sigint = getsignal(SIGINT)
    _TwoStageSigintHandler.install()
    try:
        runner = bootstrap.solver_runner()
        base_dir = bootstrap.base_dir

        benchmark_file = Path(benchmark) if benchmark else bootstrap.default_benchmark_path()
        if not benchmark_file or not benchmark_file.exists():
            msg_err = (
                "[ERRORE] Specificare il percorso del file benchmark tramite "
                "l'opzione `--benchmark <path.json>`."
            )
            secho(msg_err, fg=colors.RED, bold=True)
            return

        recipe_list = [r.strip() for r in recipes.split(",") if r.strip()] if recipes else None
        output_dir = base_dir / "output" / "runs"

        secho("\n[SOLVER] Avvio Esecuzione Benchmark", fg=colors.CYAN, bold=True)
        secho(f"  Benchmark Target: {benchmark_file}", fg=colors.WHITE)
        secho(f"  Modello Target: {model}", fg=colors.WHITE)
        secho(f"  Task Limit: {limit}", fg=colors.WHITE)
        secho(f"  Batch Size: {batch_size}", fg=colors.WHITE)
        default_rec = (
            "Tutte (text_to_schema_rag_sandbox, text_to_sql_rag_sandbox, "
            "text_to_sql_zero_shot, text_to_datalog_rag_clingo, sql_to_datalog_transpiled)"
        )
        secho(
            f"  Ricette: {', '.join(recipe_list) if recipe_list else default_rec}\n",
            fg=colors.WHITE,
        )

        run_dto = runner.run_benchmark(
            benchmark_path=benchmark_file,
            recipes=recipe_list,
            limit=limit if limit > 0 else None,
            model_role=model,
            output_dir=output_dir,
            batch_size=batch_size,
        )

        _SolverCLISummaryPresenter.print_summary(run_dto, output_dir)

    except KeyboardInterrupt:
        secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
        bootstrap.close()
        os_exit(_INTERRUPT_EXIT_CODE)
    except Exception as e:
        handle_exception(e)
    finally:
        signal(SIGINT, previous_sigint)


@app.command("stats")
def stats_command(
    ctx: Context,
    run: Annotated[
        str, Option("--run", "-r", help="ID o nome del file JSON della run di solver.")
    ] = "",
) -> None:
    """Genera la suite dei 14 grafici scientifici PNG per un file JSON di run salvato."""
    bootstrap: ApplicationBootstrap = ctx.obj
    try:
        base_dir = bootstrap.base_dir
        runs_dir = base_dir / "output" / "runs"

        if not run:
            json_files = sorted(
                runs_dir.glob("solver_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not json_files:
                msg_no_run = "[ERRORE] Nessun file di run salvato trovato in output/runs/"
                secho(msg_no_run, fg=colors.RED, bold=True)
                return
            target_json = json_files[0]
            secho(f"[INFO] Analizzo l'ultima run trovata:\n  {target_json}", fg=colors.CYAN)
        else:
            target_json = runs_dir / run if not run.endswith(".json") else Path(run)

        output_plots_dir = base_dir / "output" / "plots" / target_json.stem
        secho(f"[INFO] Avvio generazione grafici per {target_json.name}...", fg=colors.CYAN)

        analytics_svc = bootstrap.analytics()
        plots = analytics_svc.analyze_run(target_json, output_plots_dir)

        msg_done = f"\n[OK] Generati {len(plots)} grafici scientifici in:\n  {output_plots_dir}"
        secho(msg_done, fg=colors.GREEN, bold=True)
        for p in plots:
            secho(f"  - {p.name}", fg=colors.WHITE)

    except KeyboardInterrupt:
        secho(_INTERRUPT_MSG, fg=colors.YELLOW, bold=True)
    except Exception as e:
        handle_exception(e)
