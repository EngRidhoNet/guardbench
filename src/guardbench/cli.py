from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from . import __version__
from .adapters import HTTPAdapter, MockAdapter, PythonCallableAdapter, TargetAdapter
from .comparison import compare_runs
from .config import GuardBenchConfig, evaluate_gates, load_config
from .datasets import DatasetValidationError, load_dataset
from .reporting import load_report, save_junit, save_report
from .runner import run_evaluation

app = typer.Typer(
    help="Evaluate allow, block, and escalate guardrail decisions.", no_args_is_help=True
)


def _adapter(config: GuardBenchConfig) -> TargetAdapter:
    target = config.target
    if target.type == "mock":
        adapter: TargetAdapter = MockAdapter()
    elif target.type == "python":
        if not target.callable:
            raise typer.BadParameter("target.callable is required for python targets")
        adapter = PythonCallableAdapter(target.callable)
    else:
        if not target.url:
            raise typer.BadParameter("target.url is required for http targets")
        adapter = HTTPAdapter(
            target.url,
            permitted_hosts=set(target.permitted_hosts),
            allow_private=target.allow_private,
            headers=target.headers,
        )
    adapter.version = target.version
    return adapter


@app.command("version")
def version_command() -> None:
    """Print the GuardBench version."""
    typer.echo(__version__)


@app.command()
def init(
    directory: Path = typer.Argument(Path(".")),
    template: str = typer.Option("fintech", help="Starter dataset template."),
) -> None:
    """Create a local GuardBench configuration and starter dataset."""
    directory.mkdir(parents=True, exist_ok=True)
    dataset_directory = directory / "datasets"
    dataset_directory.mkdir(exist_ok=True)
    source_tree_dataset = (
        Path(__file__).resolve().parents[2] / "datasets" / "synthetic-fintech.json"
    )
    packaged_dataset = Path(__file__).parent / "templates" / "synthetic-fintech.json"
    bundled = source_tree_dataset if source_tree_dataset.exists() else packaged_dataset
    project_dataset = dataset_directory / f"synthetic-{template}.json"
    if bundled.exists() and not project_dataset.exists():
        project_dataset.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
    config_path = directory / "guardbench.yaml"
    if not config_path.exists():
        config_path.write_text(
            f"""dataset: datasets/synthetic-{template}.json
target:
  type: mock
  version: "1"
run:
  concurrency: 4
  timeout_seconds: 30
  retries: 0
quality_gates:
  minimum_macro_f1: 0.70
  maximum_indeterminate_rate: 0.05
output: .guardbench/latest.json
""",
            encoding="utf-8",
        )
    typer.echo(f"Initialized {config_path}")


@app.command()
def validate(dataset: Path) -> None:
    """Validate a JSON or CSV dataset."""
    try:
        parsed = load_dataset(dataset)
    except DatasetValidationError as exc:
        typer.echo(f"Invalid dataset: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"Valid: {parsed.name} v{parsed.version} ({len(parsed.cases)} cases)")


@app.command()
def run(config: Path = typer.Option(Path("guardbench.yaml"), exists=True)) -> None:
    """Run an evaluation and apply configured quality gates."""
    parsed = load_config(config)
    dataset_path = (config.parent / parsed.dataset).resolve()
    report = asyncio.run(run_evaluation(load_dataset(dataset_path), _adapter(parsed), parsed.run))
    output = config.parent / parsed.output
    save_report(report, output)
    failures = evaluate_gates(report.metrics, parsed.quality_gates)
    typer.echo(
        f"Completed {report.metrics['scored']}/{report.metrics['attempted']} scored | "
        f"accuracy={report.metrics['accuracy']} macro_f1={report.metrics['macro_f1']}"
    )
    typer.echo(f"Report: {output}")
    if failures:
        for failure in failures:
            typer.echo(f"GATE FAILED: {failure}", err=True)
        raise typer.Exit(4)


@app.command()
def report(
    source: Path = typer.Argument(Path(".guardbench/latest.json"), exists=True),
    format: str = typer.Option("summary", help="summary, json, or junit"),
    output: Path | None = typer.Option(None),
) -> None:
    """Render a stored run report."""
    stored = load_report(source)
    if format == "json":
        typer.echo(stored.model_dump_json(indent=2))
    elif format == "junit":
        destination = save_junit(stored, output or source.with_suffix(".xml"))
        typer.echo(str(destination))
    elif format == "summary":
        typer.echo(json.dumps(stored.metrics, indent=2))
    else:
        raise typer.BadParameter("format must be summary, json, or junit")


@app.command()
def compare(baseline: Path, candidate: Path) -> None:
    """Compare two stored run reports."""
    typer.echo(json.dumps(compare_runs(load_report(baseline), load_report(candidate)), indent=2))


if __name__ == "__main__":
    app()
