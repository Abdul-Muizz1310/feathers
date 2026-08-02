"""End-to-end: generate a service, boot it, hit /health."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml

from feathers.generator import render_service
from feathers.schema import load_schema

#: Seconds to wait for a freshly-booted generated service to answer /health.
HEALTH_DEADLINE_S = 40.0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _assert_crud_roundtrip(base: str) -> None:
    """Exercise the generated User CRUD against the live, SQLite-backed service."""
    created = httpx.post(
        f"{base}/users",
        json={"email": "a@example.com", "full_name": "Ada", "role": "editor"},
        timeout=5.0,
    )
    assert created.status_code == 201, created.text
    user = created.json()
    user_id = user["id"]
    assert user["email"] == "a@example.com"
    assert user["role"] == "editor"
    assert user["created_at"] is not None  # server_default populated via refresh

    fetched = httpx.get(f"{base}/users/{user_id}", timeout=5.0)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == user_id

    listed = httpx.get(f"{base}/users", timeout=5.0)
    assert listed.status_code == 200
    assert any(row["id"] == user_id for row in listed.json())

    missing = httpx.get(f"{base}/users/00000000-0000-0000-0000-000000000099", timeout=5.0)
    assert missing.status_code == 404


@pytest.mark.slow
def test_generate_users_service_boots_and_healthchecks(
    users_yaml_path: Path, tmp_path: Path
) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    service = tmp_path / "hello_users"

    sync = subprocess.run(["uv", "sync"], cwd=service, capture_output=True, text=True, timeout=300)
    assert sync.returncode == 0, sync.stderr

    port = _free_port()
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "hello_users.main:app",
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
        ],
        cwd=service,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Cold CI runners pay for a fresh interpreter + import graph before
        # uvicorn binds; 40s leaves headroom without hanging a broken boot.
        deadline = time.time() + HEALTH_DEADLINE_S
        last_exc: Exception | None = None
        base = f"http://127.0.0.1:{port}"
        while time.time() < deadline:
            try:
                r = httpx.get(f"{base}/health", timeout=1.0)
                if r.status_code == 200:
                    body = r.json()
                    assert body["status"] == "ok"
                    assert body["service"] == "hello_users"
                    # SQLite schema was created on startup → db probe is healthy.
                    assert body["db"] == "ok"
                    _assert_crud_roundtrip(base)
                    return
            except AssertionError:
                raise
            except Exception as exc:
                last_exc = exc
            time.sleep(0.5)
        pytest.fail(f"service did not become healthy: {last_exc}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.slow
def test_generated_service_passes_its_own_test_suite(users_yaml_path: Path, tmp_path: Path) -> None:
    """Generate the demo service and run *its* pytest suite end-to-end.

    This is the behavioral guarantee for the generated code paths the audit
    flagged as inert: the generated tests/test_platform_token.py exercises the
    per-endpoint role enforcement (401/403/200), and tests/test_users.py drives
    the CRUD + cursor-paginated list against SQLite.
    """
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    service = tmp_path / "hello_users"

    sync = subprocess.run(
        ["uv", "sync", "--all-extras"],
        cwd=service,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert sync.returncode == 0, sync.stderr

    run = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=service,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_generated_service_has_platform_middleware(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    platform = tmp_path / "hello_users" / "src" / "hello_users" / "core" / "platform.py"
    assert platform.is_file()
    text = platform.read_text()
    assert "install_platform_middleware" in text


def test_generated_ci_workflow_valid_yaml(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    ci = tmp_path / "hello_users" / ".github" / "workflows" / "ci.yml"
    assert ci.is_file()
    data = yaml.safe_load(ci.read_text())
    assert "jobs" in data
    for job in ("lint", "test", "build"):
        assert job in data["jobs"]


# Suppress unused-import warning from sys (kept for future version gating).
_ = sys
