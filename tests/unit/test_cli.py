"""Red tests for feathers.cli (Typer app)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from feathers.cli import app

runner = CliRunner()


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("new", "add", "lint", "doctor"):
        assert cmd in result.stdout


def test_new_help() -> None:
    result = runner.invoke(app, ["new", "--help"])
    assert result.exit_code == 0
    for opt in ("--schema", "--name", "--out", "--force"):
        assert opt in result.stdout


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
