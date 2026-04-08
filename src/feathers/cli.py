"""Typer CLI entry point for feathers."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from feathers.generator import add_endpoint as _add_endpoint
from feathers.generator import add_model as _add_model
from feathers.generator import render_service
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
    actions = _add_endpoint(service_dir=service, schema=parsed)
    added = sum(1 for _, a in actions if a == "added")
    typer.echo(f"ok: {added} endpoint(s) added, {len(actions) - added} unchanged")


@add_app.command("model")
def add_model_command(
    schema: Path = typer.Option(..., "--schema", "-s"),
    service: Path = typer.Option(Path("."), "--service"),
) -> None:
    """Add models from the schema to an existing service."""
    try:
        parsed = load_schema(schema)
    except SchemaError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    actions = _add_model(service_dir=service, schema=parsed)
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


@app.command("doctor")
def doctor_command() -> None:
    """Check environment prerequisites."""
    typer.echo(f"python: {sys.version.split()[0]}")
    typer.echo("ok")


@app.command("bench")
def bench_command() -> None:
    """Run Locust benchmarks — deferred."""
    typer.echo("feathers bench is coming in v0.2")
    raise typer.Exit(1)
