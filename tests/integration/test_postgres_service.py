"""Integration tier — the *generated* service running on a real Postgres.

`feathers` is a generator, so there are two different things one could test: the
generator, and the service it emits. `tests/unit/` and `tests/e2e/` cover the
generator (e2e even boots the output, but with no ``DATABASE_URL``, so it only ever
reaches the ``sqlite+aiosqlite`` fallback). This module covers the emitted service
against the database it is actually deployed on.

Three generated code paths are unreachable under SQLite and therefore untested
anywhere else:

* ``main.py``'s lifespan skips ``init_models()`` for non-SQLite dialects, so the
  schema has to come from ``alembic upgrade head`` — the same command
  ``render.yaml`` wires as Render's ``preDeployCommand``.
* ``get_engine()`` only applies ``pool_pre_ping`` / ``pool_recycle`` off SQLite.
* ``Uuid()`` becomes a native Postgres ``uuid`` and ``DateTime(timezone=True)`` a
  ``timestamptz``; keyset pagination therefore compares real UUIDs with ``>``
  rather than SQLite's ``CHAR(32)`` strings.

See ``docs/specs/05-postgres-integration.md``.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import ExecConfig

from feathers.generator import render_service
from feathers.schema import load_schema

pytestmark = pytest.mark.integration

POSTGRES_IMAGE = "postgres:17-alpine"
#: Cold `uv sync` + alembic + uvicorn boot on a fresh CI runner.
SYNC_TIMEOUT_S = 600
BOOT_DEADLINE_S = 90.0
HTTP_TIMEOUT_S = 10.0


# ── environment gate ─────────────────────────────────────────────────────────


def _docker_available() -> bool:
    """True when a Docker daemon is reachable.

    Deliberately narrow: only an absent/unreachable daemon may turn this tier into
    a skip. A daemon that answers but then fails to start Postgres is a real
    failure and must not be swallowed.
    """
    exe = shutil.which("docker")
    if exe is None:
        return False
    try:
        proc = subprocess.run(
            [exe, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


# ── helpers ──────────────────────────────────────────────────────────────────


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _run(argv: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    proc = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=SYNC_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"{' '.join(argv)} failed with {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )


@dataclass(frozen=True)
class PgService:
    """A live generated service wired to a live Postgres container."""

    base_url: str
    root: Path
    container: PostgresContainer

    def psql(self, sql: str) -> str:
        """Run ``sql`` through ``psql`` *inside* the container and return stdout.

        A second, independent client is the whole point: it is what makes "the row
        is in Postgres" an observation rather than the service confirming itself.
        """
        result = self.container.exec(
            ExecConfig(
                command=[
                    "psql",
                    "--username",
                    self.container.username,
                    "--dbname",
                    self.container.dbname,
                    "--host",
                    "127.0.0.1",
                    "--no-align",
                    "--tuples-only",
                    "-c",
                    sql,
                ],
                environment={"PGPASSWORD": self.container.password},
            )
        )
        output = result.output.decode(errors="replace")
        assert result.exit_code == 0, f"psql exited {result.exit_code}: {output}"
        return output.strip()


def _new_user_payload(role: str = "viewer") -> dict[str, str]:
    # `email` is UNIQUE in the demo schema, so every test needs a fresh one.
    return {
        "email": f"{uuid.uuid4().hex}@example.com",
        "full_name": "Integration Tester",
        "role": role,
    }


def _create_user(svc: PgService, role: str = "viewer") -> dict[str, Any]:
    response = httpx.post(
        f"{svc.base_url}/users", json=_new_user_payload(role), timeout=HTTP_TIMEOUT_S
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _list_user_ids(svc: PgService, **params: object) -> list[str]:
    response = httpx.get(f"{svc.base_url}/users", params=params, timeout=HTTP_TIMEOUT_S)
    assert response.status_code == 200, response.text
    return [str(row["id"]) for row in response.json()]


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresContainer]:
    if not _docker_available():
        pytest.skip("Docker daemon unreachable — Testcontainers integration tier skipped")
    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="module")
def pg_service(
    postgres: PostgresContainer,
    demo_users_yaml: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[PgService]:
    """Generate the demo service, migrate it onto Postgres, and boot it."""
    out_dir = tmp_path_factory.mktemp("pg_integration")
    render_service(load_schema(demo_users_yaml), out_dir=out_dir)
    root = out_dir / "hello_users"

    dsn = postgres.get_connection_url()
    assert dsn.startswith("postgresql+asyncpg://"), dsn
    env = {**os.environ, "DATABASE_URL": dsn, "GIT_SHA": "integration-tier"}

    _run(["uv", "sync"], cwd=root, env=env)
    # Postgres schema is owned by Alembic; the SQLite-only lifespan path is skipped.
    _run(["uv", "run", "alembic", "upgrade", "head"], cwd=root, env=env)

    port = _free_port()
    log_path = out_dir / "uvicorn.log"
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "hello_users.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=root,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            _await_health(proc, base_url, log_path)
            yield PgService(base_url=base_url, root=root, container=postgres)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                proc.kill()


def _await_health(proc: subprocess.Popen[bytes], base_url: str, log_path: Path) -> None:
    deadline = time.time() + BOOT_DEADLINE_S
    last_error: str = "no attempt made"
    while time.time() < deadline:
        if proc.poll() is not None:
            log = log_path.read_text(errors="replace")
            raise AssertionError(f"uvicorn exited early with {proc.returncode}\n{log}")
        try:
            response = httpx.get(f"{base_url}/health", timeout=2.0)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}: {response.text}"
        except httpx.HTTPError as exc:
            last_error = repr(exc)
        time.sleep(0.5)
    raise AssertionError(
        f"generated service never became healthy: {last_error}\n"
        f"{log_path.read_text(errors='replace')}"
    )


# ── the service really is talking to Postgres ────────────────────────────────


def test_health_reports_postgres_ok(pg_service: PgService) -> None:
    """`/health`'s `db` field is a live SELECT 1 — here, against Postgres."""
    body = httpx.get(f"{pg_service.base_url}/health", timeout=HTTP_TIMEOUT_S).json()
    assert body["status"] == "ok"
    assert body["service"] == "hello_users"
    assert body["db"] == "ok"
    assert body["commit_sha"] == "integration-tier"


def test_no_sqlite_file_was_created(pg_service: PgService) -> None:
    """Negative space: a silent SQLite fallback would make every other test a lie."""
    strays = [str(p.relative_to(pg_service.root)) for p in pg_service.root.rglob("*.db")]
    assert strays == [], f"generated service fell back to SQLite: {strays}"


def test_alembic_created_the_model_table(pg_service: PgService) -> None:
    """`alembic upgrade head` — Render's preDeployCommand — really builds the schema."""
    tables = pg_service.psql(
        "select table_name from information_schema.tables"
        " where table_schema = 'public' order by table_name"
    ).splitlines()
    assert "users" in tables
    assert "alembic_version" in tables


def test_uuid_primary_key_is_native_postgres_uuid(pg_service: PgService) -> None:
    """Generated column types survive the SQLAlchemy → Postgres mapping."""
    rows = pg_service.psql(
        "select column_name, data_type from information_schema.columns"
        " where table_name = 'users' order by column_name"
    ).splitlines()
    types = dict(line.split("|", 1) for line in rows if "|" in line)
    assert types["id"] == "uuid"
    assert types["created_at"] == "timestamp with time zone"
    # `audit: true` / `soft_delete: true` columns are emitted with the same care.
    assert types["updated_at"] == "timestamp with time zone"
    assert types["deleted_at"] == "timestamp with time zone"


def test_created_row_is_visible_to_a_separate_postgres_client(pg_service: PgService) -> None:
    created = _create_user(pg_service)
    row = pg_service.psql(
        "select email, created_at is not null, updated_at is not null"
        f" from users where id = '{created['id']}'"
    )
    assert row == f"{created['email']}|t|t", row


# ── generated CRUD against Postgres ──────────────────────────────────────────


def test_crud_roundtrip_against_postgres(pg_service: PgService) -> None:
    created = _create_user(pg_service, role="editor")
    user_id = created["id"]
    assert created["role"] == "editor"
    assert created["created_at"] is not None  # server_default, loaded via refresh

    fetched = httpx.get(f"{pg_service.base_url}/users/{user_id}", timeout=HTTP_TIMEOUT_S)
    assert fetched.status_code == 200
    assert fetched.json()["email"] == created["email"]

    assert user_id in _list_user_ids(pg_service, limit=100)

    patched = httpx.patch(
        f"{pg_service.base_url}/users/{user_id}",
        json={"full_name": "Renamed"},
        timeout=HTTP_TIMEOUT_S,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["full_name"] == "Renamed"

    missing = httpx.get(f"{pg_service.base_url}/users/{uuid.uuid4()}", timeout=HTTP_TIMEOUT_S)
    assert missing.status_code == 404


def test_soft_delete_hides_row_everywhere_but_keeps_it_in_postgres(
    pg_service: PgService,
) -> None:
    """`soft_delete: true` must retain the row yet be indistinguishable from absence."""
    created = _create_user(pg_service)
    user_id = created["id"]

    deleted = httpx.delete(f"{pg_service.base_url}/users/{user_id}", timeout=HTTP_TIMEOUT_S)
    assert deleted.status_code == 204, deleted.text

    assert user_id not in _list_user_ids(pg_service, limit=100)
    # A client that just received 204 must not still be able to read the row.
    after = httpx.get(f"{pg_service.base_url}/users/{user_id}", timeout=HTTP_TIMEOUT_S)
    assert after.status_code == 404, after.text
    # Deleting twice is not silently successful.
    again = httpx.delete(f"{pg_service.base_url}/users/{user_id}", timeout=HTTP_TIMEOUT_S)
    assert again.status_code == 404, again.text

    retained = pg_service.psql(f"select deleted_at is not null from users where id = '{user_id}'")
    assert retained == "t", f"soft delete became a hard delete: {retained!r}"


def test_cursor_pagination_pages_forward_without_repeats(pg_service: PgService) -> None:
    """Keyset pagination on a native Postgres `uuid` column, not a string."""
    mine = sorted(_create_user(pg_service)["id"] for _ in range(3))

    ordered = _list_user_ids(pg_service, limit=100)
    assert ordered == sorted(ordered), "keyset list must be ascending by primary key"

    after_first = _list_user_ids(pg_service, cursor=mine[0], limit=100)
    assert mine[0] not in after_first, "cursor must be exclusive"
    assert mine[1] in after_first
    assert mine[2] in after_first

    page = _list_user_ids(pg_service, cursor=mine[0], limit=1)
    assert len(page) == 1
    assert page[0] > mine[0]
