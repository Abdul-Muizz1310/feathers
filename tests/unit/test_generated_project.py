"""Generated-project hygiene (docs/specs/07-generated-project-hygiene.md).

Renders real schemas through the real pipeline and asserts on the emitted tree:
licence, lint/type configuration, no dead pagination code, isolated tests, and a
golden manifest that makes every change to the generated output a deliberate diff.
"""

from __future__ import annotations

import hashlib
import os
import re
import tomllib
from pathlib import Path

import pytest

from feathers.generator import render_service
from feathers.schema import load_schema
from tests.shapes import SHAPES

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "users_demo.sha256"


@pytest.fixture()
def demo(users_yaml_path: Path, tmp_path: Path) -> Path:
    render_service(load_schema(users_yaml_path), out_dir=tmp_path)
    return tmp_path / "hello_users"


def _render(shape: str, tmp_path: Path) -> Path:
    text, package = SHAPES[shape]
    render_service(load_schema(text), out_dir=tmp_path)
    return tmp_path / package


def _manifest(root: Path) -> str:
    lines = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"


# ── LICENSE ──────────────────────────────────────────────────────────────────


def test_license_is_mit_with_the_default_copyright(demo: Path) -> None:
    text = (demo / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Abdul-Muizz Anwar\n" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text


def test_license_uses_the_schema_copyright(tmp_path: Path) -> None:
    text, package = SHAPES["bare"]
    schema = load_schema(text.replace("name: bare_svc", 'name: bare_svc\n  copyright: "2027 Jane"'))
    render_service(schema, out_dir=tmp_path)
    licence = (tmp_path / package / "LICENSE").read_text(encoding="utf-8")
    assert "Copyright (c) 2027 Jane\n" in licence
    assert "Abdul-Muizz" not in licence


def test_pyproject_declares_the_license_file_that_exists(demo: Path) -> None:
    project = tomllib.loads((demo / "pyproject.toml").read_text())["project"]
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert (demo / "LICENSE").is_file()


def test_dockerfile_copies_license_before_pip_install(demo: Path) -> None:
    """hatchling refuses to build a wheel whose declared license file is missing."""
    dockerfile = (demo / "Dockerfile").read_text()
    assert dockerfile.index("LICENSE") < dockerfile.index("pip install")


# ── lint + type configuration ────────────────────────────────────────────────


def test_pyproject_carries_ruff_and_strict_mypy(demo: Path) -> None:
    data = tomllib.loads((demo / "pyproject.toml").read_text())
    ruff = data["tool"]["ruff"]
    assert ruff["line-length"] == 100
    assert ruff["src"] == ["src", "tests"]
    assert set(ruff["lint"]["select"]) == {"E", "F", "I", "B", "UP", "N", "SIM", "RUF"}
    mypy = data["tool"]["mypy"]
    assert mypy["strict"] is True
    assert mypy["files"] == ["src", "tests"]
    dev = " ".join(data["project"]["optional-dependencies"]["dev"])
    for tool in ("pytest", "ruff", "mypy"):
        assert tool in dev


def test_generated_ci_runs_ruff_and_mypy(demo: Path) -> None:
    ci = (demo / ".github" / "workflows" / "ci.yml").read_text()
    for step in ("uv run ruff check .", "uv run ruff format --check .", "uv run mypy"):
        assert step in ci


def test_generated_ci_uses_current_action_majors(demo: Path) -> None:
    ci = (demo / ".github" / "workflows" / "ci.yml").read_text()
    assert "actions/checkout@v7" in ci
    assert "astral-sh/setup-uv@v7" in ci
    assert "@v4" not in ci


# ── dead pagination code ─────────────────────────────────────────────────────


def test_cursor_only_model_has_no_offset_code(demo: Path) -> None:
    for layer in ("repositories", "services"):
        text = (demo / "src" / "hello_users" / layer / "user.py").read_text()
        assert "async def list_after(" in text
        assert "list_all" not in text
        assert "offset" not in text


def test_offset_only_model_has_no_keyset_code(tmp_path: Path) -> None:
    root = _render("offset", tmp_path)
    for layer in ("repositories", "services"):
        text = (root / "src" / "offset_svc" / layer / "item.py").read_text()
        assert "async def list_all(" in text
        assert "list_after" not in text
        assert "cursor" not in text


def test_model_without_a_list_has_no_list_code(tmp_path: Path) -> None:
    root = _render("bare", tmp_path)
    repo = (root / "src" / "bare_svc" / "repositories" / "note.py").read_text()
    service = (root / "src" / "bare_svc" / "services" / "note.py").read_text()
    for text in (repo, service):
        assert "list_all" not in text
        assert "list_after" not in text
    assert "MAX_LIMIT" not in repo
    assert "import select" not in repo


# ── isolated, re-runnable generated tests ────────────────────────────────────


def test_conftest_isolates_the_database_and_platform_settings(demo: Path) -> None:
    conftest = (demo / "tests" / "conftest.py").read_text()
    assert "tmp_path_factory" in conftest
    assert "settings.database_url" in conftest
    assert '"demo_mode", False' in conftest


def test_gitignore_ignores_sqlite_files(demo: Path) -> None:
    assert "*.db" in (demo / ".gitignore").read_text().splitlines()


def test_generated_per_model_test_proves_soft_delete_404s(demo: Path) -> None:
    text = (demo / "tests" / "test_users.py").read_text()
    body = text.split("def test_users_soft_deleted_row_is_gone(")[1].split("\ndef ")[0]
    # GET, PATCH and a second DELETE after the soft delete, each asserted to be 404.
    for verb in ('"GET"', '"PATCH"', '"DELETE"'):
        assert verb in body
    assert body.count("status_code == 404") == 3


# ── determinism + golden manifest ────────────────────────────────────────────


def test_output_carries_no_clock_or_randomness(demo: Path) -> None:
    for path in demo.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"20\d\d-\d\d-\d\d", text), f"date in {path}"


def test_rendering_twice_is_byte_identical(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    first = _manifest(tmp_path / "hello_users")
    render_service(schema, out_dir=tmp_path, force=True)
    assert _manifest(tmp_path / "hello_users") == first


def test_demo_tree_matches_the_golden_manifest(demo: Path) -> None:
    """Every change to generated output must be a deliberate, reviewed diff.

    Regenerate after an intended template change with
    ``FEATHERS_UPDATE_GOLDEN=1 uv run pytest tests/unit/test_generated_project.py``.
    """
    actual = _manifest(demo)
    if os.environ.get("FEATHERS_UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8", newline="\n")
    assert actual == GOLDEN.read_text(encoding="utf-8")
