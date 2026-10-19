"""The generated project passes its own ruff configuration, as generated.

Runs feathers' own (locked) ruff against each rendered tree, which picks up the
``[tool.ruff]`` table the generated ``pyproject.toml`` declares. Fast and offline; the
slow tier additionally runs the generated project's own ruff and mypy in its own venv.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from feathers.generator import render_service
from feathers.schema import load_schema
from tests.shapes import SHAPES


def _ruff(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _render_all(users_yaml_path: Path, tmp_path: Path) -> list[Path]:
    roots = []
    render_service(load_schema(users_yaml_path), out_dir=tmp_path)
    roots.append(tmp_path / "hello_users")
    for text, package in SHAPES.values():
        render_service(load_schema(text), out_dir=tmp_path)
        roots.append(tmp_path / package)
    return roots


@pytest.fixture()
def rendered(users_yaml_path: Path, tmp_path: Path) -> list[Path]:
    return _render_all(users_yaml_path, tmp_path)


def test_generated_code_passes_ruff_check(rendered: list[Path]) -> None:
    for root in rendered:
        result = _ruff(["check", "--no-cache", "--output-format", "concise", "."], root)
        assert result.returncode == 0, f"{root.name}:\n{result.stdout}{result.stderr}"


def test_generated_code_is_ruff_formatted(rendered: list[Path]) -> None:
    for root in rendered:
        result = _ruff(["format", "--no-cache", "--check", "--diff", "."], root)
        assert result.returncode == 0, f"{root.name}:\n{result.stdout}{result.stderr}"
