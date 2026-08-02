"""Typer CLI entry point for feathers."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import typer

from feathers.bench import DEFAULT_ITERATIONS, format_report, run_benchmark
from feathers.generator import PatcherError, render_service
from feathers.generator import add_endpoint as _add_endpoint
from feathers.generator import add_model as _add_model
from feathers.schema import SchemaError, load_schema

app = typer.Typer(
    help="Scaffold production FastAPI services from YAML.",
    no_args_is_help=True,
    add_completion=False,
)
add_app = typer.Typer(help="Add to an existing service.", no_args_is_help=True)
app.add_typer(add_app, name="add")


@app.command("new")
def new_command(
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to YAML schema."),
    name: str = typer.Option(..., "--name", "-n", help="Service name (snake_case)."),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Output directory."),
    force: bool = typer.Option(False, "--force", help="Overwrite if the target exists."),
) -> None:
    """Generate a new service from a YAML schema."""
    try:
        parsed = load_schema(schema)
    except SchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if parsed.service.name != name:
        typer.echo(
            f"warning: --name '{name}' differs from schema service.name '{parsed.service.name}';"
            f" using '{parsed.service.name}'",
            err=True,
        )

    try:
        render_service(parsed, out_dir=out, force=force)
    except FileExistsError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"ok: generated {parsed.service.name} in {out}")


@add_app.command("endpoint")
def add_endpoint_command(
    schema: Path = typer.Option(..., "--schema", "-s"),
    service: Path = typer.Option(Path("."), "--service"),
) -> None:
    """Add endpoints from the schema to an existing service."""
    try:
        parsed = load_schema(schema)
    except SchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    try:
        actions = _add_endpoint(service_dir=service, schema=parsed)
    except PatcherError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    added = sum(1 for _, a in actions if a == "added")
    typer.echo(f"ok: {added} endpoint(s) added, {len(actions) - added} unchanged")


@add_app.command("model")
def add_model_command(
    schema: Path = typer.Option(..., "--schema", "-s"),
    service: Path = typer.Option(Path("."), "--service"),
) -> None:
    """Scaffold an empty model-stub file for each new model, to fill in by hand.

    Unlike ``feathers new`` (which emits a fully wired SQLAlchemy model +
    Pydantic schemas + repository + service + router), ``add model`` only
    writes a bare dataclass placeholder and does not wire it into the app.
    """
    try:
        parsed = load_schema(schema)
    except SchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    try:
        actions = _add_model(service_dir=service, schema=parsed)
    except PatcherError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    added = sum(1 for _, a in actions if a == "added")
    typer.echo(f"ok: {added} model(s) added, {len(actions) - added} unchanged")


@app.command("lint")
def lint_command(schema: Path = typer.Argument(...)) -> None:
    """Validate a YAML schema without generating."""
    try:
        load_schema(schema)
    except SchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo("ok: schema valid")


def _uv_version() -> str | None:
    """Return the installed ``uv`` version, or ``None`` when uv is unusable.

    "Unusable" deliberately covers more than "absent from ``PATH``": a resolved
    binary that cannot be executed, exits non-zero, or prints nothing is just as
    useless to a generated (uv-managed) service, so it is reported the same way.
    """
    exe = shutil.which("uv")
    if exe is None:
        return None
    try:
        # `exe` is an absolute path resolved by shutil.which; argv is fixed.
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


@app.command("doctor")
def doctor_command() -> None:
    """Check environment prerequisites (Python, uv)."""
    typer.echo(f"python: {sys.version.split()[0]}")
    uv = _uv_version()
    typer.echo(f"uv: {uv if uv else 'not found'}")
    if uv is None:
        typer.echo(
            "error: uv is required — every generated service is uv-managed"
            " (`uv sync`, `uv run`); install it from https://docs.astral.sh/uv/",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo("ok")


@app.command("bench")
def bench_command(
    iterations: int = typer.Option(
        DEFAULT_ITERATIONS,
        "--iterations",
        "-n",
        min=1,
        help="Number of services to scaffold and time.",
    ),
) -> None:
    """Measure service-generation throughput by scaffolding the demo schema."""
    result = run_benchmark(iterations)
    typer.echo(format_report(result))
