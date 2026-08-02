"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMOS_DIR = REPO_ROOT / "src" / "feathers" / "demos"


@pytest.fixture(scope="session")
def demo_users_yaml() -> Path:
    """Session-scoped path to the bundled demo schema (read-only).

    Exists so session/module-scoped fixtures (the Postgres integration tier) can
    reach the demo schema without widening the function-scoped alias below.
    """
    return DEMOS_DIR / "users.yaml"


@pytest.fixture()
def users_yaml_path(demo_users_yaml: Path) -> Path:
    return demo_users_yaml


@pytest.fixture()
def minimal_yaml_text() -> str:
    return """\
service:
  name: minimal
  description: Minimal test service
models:
  - name: Thing
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: label, type: str, max_length: 50 }
endpoints:
  - { method: GET, path: "/things/{id}", handler: things.get, auth: none }
"""
