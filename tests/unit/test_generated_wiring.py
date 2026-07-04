"""Integration tests that render the demo service and assert the composed
output actually wires the features the schema declares.

These drive the real render path (schema -> context -> renderer -> files) and
guard against the "validated-but-inert" regressions the audit flagged: auth
roles, cursor pagination, bounded list limits, CORS, serverless-safe pooling,
and a deployable Docker/Render toolchain.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from feathers.generator import render_service
from feathers.schema import load_schema


@pytest.fixture()
def service_root(users_yaml_path: Path, tmp_path: Path) -> Path:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    return tmp_path / "hello_users"


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


# ── auth role enforcement (CRITICAL) ─────────────────────────────────────────


def test_router_wires_require_role_per_endpoint(service_root: Path) -> None:
    router = _read(service_root, "src/hello_users/api/routers/users.py")
    assert "from hello_users.core.platform_token import require_role" in router
    # POST /users is declared `auth: admin` in the demo schema.
    assert 'require_role("admin")' in router
    # GET /users/{id} is `auth: any`.
    assert 'require_role("any")' in router


def test_platform_token_defines_role_dependency(service_root: Path) -> None:
    pt = _read(service_root, "src/hello_users/core/platform_token.py")
    assert "def require_role(" in pt
    # A genuine role comparison (not just a signature check) with a 403 path.
    assert "_ROLE_RANK" in pt
    assert "status_code=403" in pt
    # It must actually decode the token's claims, not only verify the signature.
    assert "jwt.decode(" in pt
    assert 'claims.get("role"' in pt


def test_endpoint_without_auth_has_no_guard() -> None:
    """An `auth: none` endpoint must NOT get a require_role dependency."""
    from feathers.schema import load_schema as _ls

    schema = _ls(
        """
service:
  name: pub_svc
models:
  - name: Item
    fields:
      - { name: id, type: uuid, primary: true }
endpoints:
  - { method: GET, path: "/items/{id}", handler: items.get, auth: none }
"""
    )
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        render_service(schema, out_dir=Path(d))
        router = (
            Path(d) / "pub_svc" / "src" / "pub_svc" / "api" / "routers" / "items.py"
        ).read_text()
    assert "require_role" not in router.split("router = APIRouter")[1]


# ── paginate: cursor (HIGH) ──────────────────────────────────────────────────


def test_cursor_pagination_signature_differs_from_offset(
    users_yaml_path: Path, tmp_path: Path
) -> None:
    # Demo GET /users declares paginate: cursor.
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    cursor_router = (
        tmp_path / "hello_users" / "src" / "hello_users" / "api" / "routers" / "users.py"
    ).read_text()
    assert "cursor:" in cursor_router
    assert "service.list_after(" in cursor_router

    # Same schema but offset pagination → different signature.
    offset_schema = load_schema(
        """
service:
  name: off_svc
models:
  - name: Item
    fields:
      - { name: id, type: uuid, primary: true }
endpoints:
  - { method: GET, path: "/items", handler: items.list, paginate: offset }
"""
    )
    out2 = tmp_path / "offset"
    render_service(offset_schema, out_dir=out2)
    offset_router = (
        out2 / "off_svc" / "src" / "off_svc" / "api" / "routers" / "items.py"
    ).read_text()
    assert "offset:" in offset_router
    assert "cursor:" not in offset_router
    assert "service.list_all(" in offset_router


def test_repository_emits_cursor_and_offset_methods(service_root: Path) -> None:
    repo = _read(service_root, "src/hello_users/repositories/user.py")
    assert "async def list_all(" in repo
    assert "async def list_after(" in repo
    assert "User.id > cursor" in repo  # genuine keyset predicate


# ── COST-1: bounded limit ────────────────────────────────────────────────────


def test_list_limit_is_bounded(service_root: Path) -> None:
    router = _read(service_root, "src/hello_users/api/routers/users.py")
    assert "Query(50, ge=1, le=100)" in router
    repo = _read(service_root, "src/hello_users/repositories/user.py")
    assert "MAX_LIMIT" in repo
    assert "_clamp_limit(" in repo


# ── COR-1: CORS middleware ───────────────────────────────────────────────────


def test_cors_middleware_wired(service_root: Path) -> None:
    platform = _read(service_root, "src/hello_users/core/platform.py")
    assert "from fastapi.middleware.cors import CORSMiddleware" in platform
    assert "app.add_middleware(" in platform
    assert "settings.cors_origins" in platform


# ── REL-2: serverless-safe pooling ───────────────────────────────────────────


def test_engine_uses_pre_ping_and_recycle(service_root: Path) -> None:
    db = _read(service_root, "src/hello_users/core/db.py")
    assert "pool_pre_ping" in db
    assert "pool_recycle" in db
    # SQLite must not receive the Postgres-only pool kwargs.
    assert 'not url.startswith("sqlite")' in db


# ── REL-1 / SEC-1 / P12: deployable Docker + Render toolchain ────────────────


def test_render_predeploy_does_not_use_uv(service_root: Path) -> None:
    render_yaml = _read(service_root, "render.yaml")
    assert "alembic upgrade head" in render_yaml
    assert "uv run" not in render_yaml


def test_dockerfile_copies_alembic_and_runs_nonroot(service_root: Path) -> None:
    dockerfile = _read(service_root, "Dockerfile")
    assert "COPY alembic" in dockerfile
    assert "alembic.ini" in dockerfile
    assert "USER app" in dockerfile


# ── OPT-1: observability config is consumed, not inert ───────────────────────


def test_structlog_configured_when_selected(service_root: Path) -> None:
    platform = _read(service_root, "src/hello_users/core/platform.py")
    assert "def configure_logging(" in platform
    assert "structlog.configure(" in platform
    main = _read(service_root, "src/hello_users/main.py")
    assert "configure_logging()" in main


def test_no_inert_opentelemetry_surface(service_root: Path) -> None:
    """OPT-1: `otel`/OpenTelemetry is neither claimed nor a dependency anywhere.

    The schema no longer exposes a `tracing` option, and no generated file may
    mention OpenTelemetry — otherwise we'd be back to advertising tracing the
    templates never wire.
    """
    for path in service_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        assert "opentelemetry" not in text, f"{path} references opentelemetry"
        assert "otel" not in text, f"{path} references otel"


def test_stdlib_logging_omits_structlog_dependency(tmp_path: Path) -> None:
    schema = load_schema(
        """
service:
  name: plain_svc
models:
  - name: Item
    fields:
      - { name: id, type: uuid, primary: true }
observability:
  metrics: none
  logging: stdlib
"""
    )
    render_service(schema, out_dir=tmp_path)
    root = tmp_path / "plain_svc"
    pyproject = (root / "pyproject.toml").read_text()
    assert "structlog" not in pyproject
    assert "prometheus-fastapi-instrumentator" not in pyproject
    platform = (root / "src" / "plain_svc" / "core" / "platform.py").read_text()
    assert "import structlog" not in platform
    assert "Instrumentator()" not in platform
    # Every generated module must still be syntactically valid.
    for p in root.rglob("*.py"):
        ast.parse(p.read_text(encoding="utf-8"))
