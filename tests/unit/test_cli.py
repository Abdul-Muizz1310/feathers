"""Red tests for feathers.cli (Typer app)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from feathers import cli
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
    """`doctor` reports both prerequisites it advertises: Python *and* uv."""
    result = runner.invoke(app, ["doctor"])
    out = _plain(result.stdout).lower()
    assert result.exit_code == 0, out
    assert "python" in out
    assert "uv" in out
    assert "not found" not in out
    assert "ok" in out


def test_doctor_reports_uv_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reported uv line carries the version `uv --version` printed."""
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/uv")
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "uv 9.9.9 (abcdef)\n", ""),
    )
    result = runner.invoke(app, ["doctor"])
    out = _plain(result.stdout)
    assert result.exit_code == 0, out
    assert "uv 9.9.9 (abcdef)" in out


def test_doctor_exits_one_when_uv_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing prerequisite must never be reported as `ok`."""
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)
    result = runner.invoke(app, ["doctor"])
    out = _plain(result.stdout)
    assert result.exit_code == 1, out
    assert "uv: not found" in out
    assert "ok" not in out


@pytest.mark.parametrize(
    "outcome",
    [
        "nonzero",
        "oserror",
        "empty",
    ],
)
def test_doctor_exits_one_when_uv_version_fails(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """uv on PATH but unusable is still a missing prerequisite."""
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/uv")

    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        if outcome == "oserror":
            raise OSError("exec format error")
        code = 1 if outcome == "nonzero" else 0
        stdout = "" if outcome in {"nonzero", "empty"} else "uv 1.0.0"
        return subprocess.CompletedProcess(["uv"], code, stdout, "boom")

    monkeypatch.setattr(cli.subprocess, "run", _run)
    result = runner.invoke(app, ["doctor"])
    out = _plain(result.stdout)
    assert result.exit_code == 1, out
    assert "uv: not found" in out
    assert "ok" not in out


def test_bench_reports_generation_speed() -> None:
    """`feathers bench` scaffolds the demo and prints generation-speed metrics."""
    result = runner.invoke(app, ["bench", "--iterations", "2"])
    assert result.exit_code == 0, _plain(result.stdout)
    out = _plain(result.stdout)
    assert "services generated: 2" in out
    assert "ms" in out
    assert "gen/s" in out


def test_bench_rejects_zero_iterations() -> None:
    """Cover the Typer `min=1` guard on --iterations."""
    result = runner.invoke(app, ["bench", "--iterations", "0"])
    assert result.exit_code != 0


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


def test_add_endpoint_nonexistent_service_exits_1(users_yaml_path: Path, tmp_path: Path) -> None:
    """A bad --service path must surface a clean CLI error, not a raw traceback.

    Regression for the uncaught PatcherError crash: the generator raises
    PatcherError, and the CLI must translate it to `error: ...` + exit 1.
    """
    result = runner.invoke(
        app,
        [
            "add",
            "endpoint",
            "--schema",
            str(users_yaml_path),
            "--service",
            str(tmp_path / "does-not-exist"),
        ],
    )
    assert result.exit_code == 1
    combined = _plain(result.stdout) + _plain(result.stderr or "")
    assert "error:" in combined
    assert "service dir not found" in combined
    # The raw exception type must never leak to the user.
    assert "Traceback" not in combined
    assert "PatcherError" not in combined


def test_add_model_nonexistent_service_exits_1(users_yaml_path: Path, tmp_path: Path) -> None:
    """`add model` against a bad --service path exits 1 with a clean error."""
    result = runner.invoke(
        app,
        [
            "add",
            "model",
            "--schema",
            str(users_yaml_path),
            "--service",
            str(tmp_path / "does-not-exist"),
        ],
    )
    assert result.exit_code == 1
    combined = _plain(result.stdout) + _plain(result.stderr or "")
    assert "error:" in combined
    assert "Traceback" not in combined


def test_add_endpoint_happy(users_yaml_path: Path, tmp_path: Path) -> None:
    """Cover cli.py:65-67 — add endpoint on generated service."""
    # First generate a service
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
    # Then add endpoints (should be idempotent)
    result = runner.invoke(
        app,
        [
            "add",
            "endpoint",
            "--schema",
            str(users_yaml_path),
            "--service",
            str(tmp_path / "hello_users"),
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
            "add",
            "model",
            "--schema",
            str(users_yaml_path),
            "--service",
            str(tmp_path / "hello_users"),
        ],
    )
    assert result.exit_code == 0, _plain(result.stdout)
    assert "ok" in _plain(result.stdout).lower()
