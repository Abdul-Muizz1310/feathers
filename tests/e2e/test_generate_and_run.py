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


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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
        deadline = time.time() + 20
        last_exc: Exception | None = None
        while time.time() < deadline:
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
                if r.status_code == 200:
                    body = r.json()
                    assert body["status"] == "ok"
                    assert body["service"] == "hello_users"
                    return
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
