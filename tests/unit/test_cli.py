"""Red tests for feathers.cli (Typer app)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from feathers.cli import app

# mix_stderr is removed in newer Typer; keep runner simple.
runner = CliRunner()


def _plain(text: str) -> str:
    """Strip ANSI escape sequences so tests don't care about Rich styling."""
    import re

    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = _plain(result.stdout)
    for cmd in ("new", "add", "lint", "doctor"):
        assert cmd in out


def test_new_help() -> None:
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    out = _plain(result.stdout)
    # Rich may wrap and break option strings across lines; look for the short forms too.
    assert "schema" in out and ("-s" in out or "--schema" in out)
    assert "name" in out
    assert "out" in out
    assert "force" in out


def test_new_creates_service_dir(users_yaml_path: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--schema",
            str(users_yaml_path),
            "--name",
            "hello_users",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    service = tmp_path / "hello_users"
    assert (service / "pyproject.toml").is_file()
    assert (service / "src" / "hello_users" / "main.py").is_file()


def test_new_refuses_overwrite_without_force(users_yaml_path: Path, tmp_path: Path) -> None:
    (tmp_path / "hello_users").mkdir()
    result = runner.invoke(
        app,
        [
            "new",
            "--schema",
            str(users_yaml_path),
            "--name",
            "hello_users",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1


def test_new_with_force_overwrites(users_yaml_path: Path, tmp_path: Path) -> None:
    runner.invoke(
        app,
        [
            "new",
            "--schema",
            str(users_yaml_path),
            "--name",
            "hello_users",
            "--out",
            str(tmp_path),
        ],
    )
    result = runner.invoke(
        app,
        [
            "new",
            "--schema",
            str(users_yaml_path),
            "--name",
            "hello_users",
            "--out",
            str(tmp_path),
            "--force",
        ],
    )
    assert result.exit_code == 0


def test_new_missing_schema_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--schema",
            str(tmp_path / "nope.yaml"),
            "--name",
            "x",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1


def test_lint_valid_yaml_exit_zero(users_yaml_path: Path) -> None:
    result = runner.invoke(app, ["lint", str(users_yaml_path)])
    assert result.exit_code == 0
    assert "ok" in result.stdout.lower()


def test_lint_invalid_yaml_exit_one(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("service: [unclosed")
    result = runner.invoke(app, ["lint", str(bad)])
    assert result.exit_code == 1


def test_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "python" in result.stdout.lower()


def test_bench_deferred() -> None:
    result = runner.invoke(app, ["bench"])
    assert result.exit_code != 0
    assert "v0.2" in result.stdout or "v0.2" in (result.stderr or "")


# ---------------------------------------------------------------------------
# Coverage gap tests
# ---------------------------------------------------------------------------


def test_new_name_mismatch_warning(users_yaml_path: Path, tmp_path: Path) -> None:
    """Cover cli.py:39 — --name differs from schema service.name."""
    result = runner.invoke(
        app,
        [
            "new",
            "--schema",
            str(users_yaml_path),
            "--name",
            "wrong_name",  # schema says "hello_users"
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    combined = _plain(result.stdout).lower() + _plain(result.stderr or "").lower()
    assert "warning" in combined


def test_add_endpoint_schema_error_exits_1(tmp_path: Path) -> None:
    """Cover cli.py:60-67 — add endpoint with bad schema → exit 1."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("not valid schema")
    result = runner.invoke(
        app,
        ["add", "endpoint", "--schema", str(bad), "--service", str(tmp_path)],
    )
    assert result.exit_code == 1


def test_add_model_schema_error_exits_1(tmp_path: Path) -> None:
    """Cover cli.py:76-83 — add model with bad schema → exit 1."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("not valid schema")
    result = runner.invoke(
        app,
        ["add", "model", "--schema", str(bad), "--service", str(tmp_path)],
    )
    assert result.exit_code == 1


def test_add_endpoint_happy(users_yaml_path: Path, tmp_path: Path) -> None:
    """Cover cli.py:65-67 — add endpoint on generated service."""
    # First generate a service
    runner.invoke(
        app,
        [
            "new",
            "--schema", str(users_yaml_path),
            "--name", "hello_users",
            "--out", str(tmp_path),
        ],
    )
    # Then add endpoints (should be idempotent)
    result = runner.invoke(
        app,
        [
            "add", "endpoint",
            "--schema", str(users_yaml_path),
            "--service", str(tmp_path / "hello_users"),
        ],
    )
    assert result.exit_code == 0, _plain(result.stdout)
    assert "ok" in _plain(result.stdout).lower()


def test_add_model_happy(users_yaml_path: Path, tmp_path: Path) -> None:
    """Cover cli.py:81-83 — add model on generated service."""
    runner.invoke(
        app,
        [
            "new",
            "--schema", str(users_yaml_path),
            "--name", "hello_users",
            "--out", str(tmp_path),
        ],
    )
    result = runner.invoke(
        app,
        [
            "add", "model",
            "--schema", str(users_yaml_path),
            "--service", str(tmp_path / "hello_users"),
        ],
    )
    assert result.exit_code == 0, _plain(result.stdout)
    assert "ok" in _plain(result.stdout).lower()
