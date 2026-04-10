"""Red tests for feathers.generator.ast_patcher — incremental mode."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from feathers.generator import PatcherError, add_endpoint, add_model, render_service
from feathers.schema import load_schema


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bootstrap_service(users_yaml_path: Path, tmp_path: Path) -> Path:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    return tmp_path / "hello_users"


EXTRA_ENDPOINT_YAML = """\
service:
  name: hello_users
models:
  - name: User
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: email, type: str }
endpoints:
  - { method: POST, path: "/users", handler: users.create, auth: admin }
  - { method: GET,  path: "/users/{id}", handler: users.get, auth: any }
  - { method: GET,  path: "/users/{id}/audit", handler: users.audit, auth: admin }
"""


def test_adds_new_endpoint_function(users_yaml_path: Path, tmp_path: Path) -> None:
    service = _bootstrap_service(users_yaml_path, tmp_path)
    router = service / "src" / "hello_users" / "api" / "routers" / "users.py"
    before = router.read_text()
    new_schema = load_schema(EXTRA_ENDPOINT_YAML)
    actions = add_endpoint(service_dir=service, schema=new_schema)
    after = router.read_text()
    assert "audit" in after
    assert before != after
    assert any(a == "added" for _, a in actions)


def test_idempotent_add_endpoint(users_yaml_path: Path, tmp_path: Path) -> None:
    service = _bootstrap_service(users_yaml_path, tmp_path)
    router = service / "src" / "hello_users" / "api" / "routers" / "users.py"
    new_schema = load_schema(EXTRA_ENDPOINT_YAML)
    add_endpoint(service_dir=service, schema=new_schema)
    first = _sha(router)
    actions = add_endpoint(service_dir=service, schema=new_schema)
    second = _sha(router)
    assert first == second
    assert all(a == "unchanged" for _, a in actions)


def test_preserves_hand_written_fence(users_yaml_path: Path, tmp_path: Path) -> None:
    service = _bootstrap_service(users_yaml_path, tmp_path)
    router = service / "src" / "hello_users" / "api" / "routers" / "users.py"
    original = router.read_text()
    fence = (
        "\n# feathers: begin hand-written\nHAND_WRITTEN_CONST = 42\n# feathers: end hand-written\n"
    )
    router.write_text(original + fence)
    new_schema = load_schema(EXTRA_ENDPOINT_YAML)
    add_endpoint(service_dir=service, schema=new_schema)
    after = router.read_text()
    assert "HAND_WRITTEN_CONST = 42" in after
    assert "# feathers: begin hand-written" in after
    assert "# feathers: end hand-written" in after


EXTRA_MODEL_YAML = """\
service:
  name: hello_users
models:
  - name: User
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: email, type: str }
  - name: Session
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: token, type: str }
endpoints: []
"""


def test_adds_new_model_class(users_yaml_path: Path, tmp_path: Path) -> None:
    service = _bootstrap_service(users_yaml_path, tmp_path)
    new_schema = load_schema(EXTRA_MODEL_YAML)
    add_model(service_dir=service, schema=new_schema)
    session_file = service / "src" / "hello_users" / "models" / "session.py"
    assert session_file.is_file()


def test_add_model_is_idempotent(users_yaml_path: Path, tmp_path: Path) -> None:
    service = _bootstrap_service(users_yaml_path, tmp_path)
    new_schema = load_schema(EXTRA_MODEL_YAML)
    add_model(service_dir=service, schema=new_schema)
    session_file = service / "src" / "hello_users" / "models" / "session.py"
    first = _sha(session_file)
    add_model(service_dir=service, schema=new_schema)
    assert _sha(session_file) == first


def test_add_to_nonexistent_service_raises(tmp_path: Path) -> None:
    schema = load_schema(EXTRA_ENDPOINT_YAML)
    with pytest.raises(PatcherError):
        add_endpoint(service_dir=tmp_path / "nope", schema=schema)


def test_add_endpoint_missing_routers_dir_raises(tmp_path: Path) -> None:
    """Cover ast_patcher.py:50 — routers dir not found."""
    # Create a valid-looking service dir without a routers subdir
    schema = load_schema(EXTRA_ENDPOINT_YAML)
    service = tmp_path / "fake_svc"
    (service / "src" / "hello_users" / "api").mkdir(parents=True)
    # No "routers" directory inside api/
    with pytest.raises(PatcherError, match="routers dir not found"):
        add_endpoint(service_dir=service, schema=schema)


def test_add_endpoint_skips_model_without_router_file(
    users_yaml_path: Path, tmp_path: Path
) -> None:
    """Cover ast_patcher.py:56 — router file doesn't exist → skip."""
    service = _bootstrap_service(users_yaml_path, tmp_path)
    # Remove the generated router file
    router = service / "src" / "hello_users" / "api" / "routers" / "users.py"
    router.unlink()
    # add_endpoint should not crash — just return no actions for this model
    schema = load_schema(EXTRA_ENDPOINT_YAML)
    actions = add_endpoint(service_dir=service, schema=schema)
    assert all(a == "unchanged" or a == "added" for _, a in actions) or len(actions) == 0


def test_add_model_to_nonexistent_service_raises(tmp_path: Path) -> None:
    """Cover ast_patcher.py:71 — service dir not found for add_model."""
    schema = load_schema(EXTRA_MODEL_YAML)
    with pytest.raises(PatcherError, match="not found"):
        add_model(service_dir=tmp_path / "nope", schema=schema)
