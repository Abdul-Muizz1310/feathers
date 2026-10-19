"""End-to-end: generate a service, boot it, drive it with contract-v2 tokens."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest
import yaml

from feathers.generator import render_service
from feathers.schema import load_schema
from tests.shapes import KITCHEN
from tests.tokens import BastionKey

#: Seconds to wait for a freshly-booted generated service to answer /health.
HEALTH_DEADLINE_S = 40.0
#: The demo schema's service name is ``hello_users`` → audience ``hello-users``.
DEMO_AUD = "hello-users"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=600)


def _assert_crud_roundtrip(base: str, key: BastionKey) -> None:
    """Exercise the generated User CRUD against the live, SQLite-backed service."""
    admin = key.headers(aud=DEMO_AUD, role="admin")

    # Contract v2: a protected route without a token is refused, not served.
    anonymous = httpx.get(f"{base}/users", timeout=5.0)
    assert anonymous.status_code == 401, anonymous.text
    assert anonymous.json() == {"detail": "missing_platform_token"}
    # A token minted for another service is refused too.
    foreign = httpx.get(f"{base}/users", headers=key.headers(aud="magpie"), timeout=5.0)
    assert foreign.status_code == 401
    assert foreign.json() == {"detail": "invalid_platform_token"}

    created = httpx.post(
        f"{base}/users",
        json={"email": "a@example.com", "full_name": "Ada", "role": "editor"},
        headers=admin,
        timeout=5.0,
    )
    assert created.status_code == 201, created.text
    user = created.json()
    user_id = user["id"]
    assert user["email"] == "a@example.com"
    assert user["role"] == "editor"
    assert user["created_at"] is not None  # server_default populated via refresh

    # POST /users is `auth: admin`; a viewer is authenticated but not allowed.
    viewer = key.headers(aud=DEMO_AUD, role="viewer")
    forbidden = httpx.post(
        f"{base}/users",
        json={"email": "b@example.com", "full_name": "Bo"},
        headers=viewer,
        timeout=5.0,
    )
    assert forbidden.status_code == 403, forbidden.text

    fetched = httpx.get(f"{base}/users/{user_id}", headers=viewer, timeout=5.0)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == user_id

    listed = httpx.get(f"{base}/users", headers=viewer, timeout=5.0)
    assert listed.status_code == 200
    assert any(row["id"] == user_id for row in listed.json())

    missing = httpx.get(
        f"{base}/users/00000000-0000-0000-0000-000000000099", headers=admin, timeout=5.0
    )
    assert missing.status_code == 404

    # Soft delete: 204 once, then the row is gone to every path.
    assert httpx.delete(f"{base}/users/{user_id}", headers=admin, timeout=5.0).status_code == 204
    assert httpx.get(f"{base}/users/{user_id}", headers=admin, timeout=5.0).status_code == 404
    assert httpx.delete(f"{base}/users/{user_id}", headers=admin, timeout=5.0).status_code == 404
    gone = httpx.get(f"{base}/users", headers=admin, timeout=5.0).json()
    assert all(row["id"] != user_id for row in gone)


@pytest.mark.slow
def test_generate_users_service_boots_and_healthchecks(
    users_yaml_path: Path, tmp_path: Path
) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    service = tmp_path / "hello_users"
    key = BastionKey()

    sync = _run(["uv", "sync"], service)
    assert sync.returncode == 0, sync.stderr

    port = _free_port()
    env = {**os.environ, "BASTION_SIGNING_KEY_PUBLIC": key.public_b64}
    env.pop("DEMO_MODE", None)
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
        env=env,
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
                    _assert_crud_roundtrip(base, key)
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
@pytest.mark.parametrize("shape", ["users", "kitchen"])
def test_generated_service_passes_its_own_gates(
    shape: str, users_yaml_path: Path, tmp_path: Path
) -> None:
    """Generate a service and run *its* lint, type and test gates in its own venv.

    This is the behavioural guarantee for the emitted code: the generated
    ``tests/test_platform_token.py`` holds the contract-v2 conformance cases and the
    per-model tests drive CRUD (soft delete included) with minted tokens. The suite
    runs twice — the second run proves it is isolated and re-runnable.
    """
    schema = load_schema(users_yaml_path if shape == "users" else KITCHEN)
    render_service(schema, out_dir=tmp_path)
    service = tmp_path / schema.service.name

    sync = _run(["uv", "sync", "--all-extras"], service)
    assert sync.returncode == 0, sync.stderr

    for gate in (
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "mypy"],
        ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider"],
        ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider"],
    ):
        result = _run(gate, service)
        assert result.returncode == 0, f"{' '.join(gate)}\n{result.stdout}{result.stderr}"

    # Tool caches (.venv, .mypy_cache — mypy 2 caches in SQLite) are not the service's.
    strays = [
        str(p.relative_to(service))
        for p in service.rglob("*.db")
        if not any(part.startswith(".") for part in p.relative_to(service).parts)
    ]
    assert strays == [], f"generated tests left a database in the project: {strays}"


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
