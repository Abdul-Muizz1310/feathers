"""Red tests for feathers.schema — YAML validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from feathers.schema import SchemaError, ServiceSchema, load_schema


# ── Success ─────────────────────────────────────────────────────────────────


def test_parses_minimal_valid_yaml(minimal_yaml_text: str) -> None:
    schema = load_schema(minimal_yaml_text)
    assert isinstance(schema, ServiceSchema)
    assert schema.service.name == "minimal"
    assert len(schema.models) == 1
    assert schema.models[0].name == "Thing"


def test_parses_full_users_demo(users_yaml_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    assert schema.service.name == "hello_users"
    assert any(m.name == "User" for m in schema.models)
    assert any(e.path == "/users" and e.method == "POST" for e in schema.endpoints)


def test_parses_enum_field_with_values(minimal_yaml_text: str) -> None:
    src = minimal_yaml_text.replace(
        "{ name: label, type: str, max_length: 50 }",
        "{ name: role, type: enum, values: [admin, editor, viewer] }",
    )
    schema = load_schema(src)
    role = next(f for f in schema.models[0].fields if f.name == "role")
    assert role.type == "enum"
    assert role.values == ["admin", "editor", "viewer"]


def test_observability_defaults(minimal_yaml_text: str) -> None:
    schema = load_schema(minimal_yaml_text)
    assert schema.observability.metrics == "prometheus"
    assert schema.observability.tracing == "otel"
    assert schema.observability.logging == "structlog"


def test_deploy_defaults(minimal_yaml_text: str) -> None:
    schema = load_schema(minimal_yaml_text)
    assert schema.deploy.target == "render"
    assert schema.deploy.health == "/health"


def test_service_schema_is_frozen(minimal_yaml_text: str) -> None:
    schema = load_schema(minimal_yaml_text)
    with pytest.raises((TypeError, ValueError)):
        schema.service.name = "other"  # type: ignore[misc]


# ── Failure ─────────────────────────────────────────────────────────────────


def test_missing_service_key() -> None:
    with pytest.raises(SchemaError, match="service"):
        load_schema("models:\n  - name: X\n    fields: []\n")


def test_missing_models_key() -> None:
    with pytest.raises(SchemaError, match="models"):
        load_schema("service:\n  name: x\n")


def test_empty_models_list() -> None:
    with pytest.raises(SchemaError):
        load_schema("service:\n  name: x\nmodels: []\n")


def test_unknown_field_type() -> None:
    src = """\
service: { name: x }
models:
  - name: Thing
    fields:
      - { name: id, type: money }
"""
    with pytest.raises(SchemaError, match="money|type"):
        load_schema(src)


def test_enum_without_values() -> None:
    src = """\
service: { name: x }
models:
  - name: Thing
    fields:
      - { name: role, type: enum }
"""
    with pytest.raises(SchemaError, match="enum"):
        load_schema(src)


def test_duplicate_field_names() -> None:
    src = """\
service: { name: x }
models:
  - name: Thing
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: id, type: str }
"""
    with pytest.raises(SchemaError, match="duplicate"):
        load_schema(src)


def test_endpoint_path_missing_leading_slash() -> None:
    src = """\
service: { name: x }
models:
  - name: Thing
    fields:
      - { name: id, type: uuid, primary: true }
endpoints:
  - { method: GET, path: things, handler: t.get }
"""
    with pytest.raises(SchemaError, match="path"):
        load_schema(src)


def test_unknown_http_method() -> None:
    src = """\
service: { name: x }
models:
  - name: Thing
    fields:
      - { name: id, type: uuid, primary: true }
endpoints:
  - { method: FETCH, path: /things, handler: t.get }
"""
    with pytest.raises(SchemaError, match="FETCH|method"):
        load_schema(src)


def test_unreadable_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(SchemaError, match="nope.yaml"):
        load_schema(missing)


def test_empty_yaml_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("")
    with pytest.raises(SchemaError, match="empty"):
        load_schema(p)


def test_malformed_yaml() -> None:
    with pytest.raises(SchemaError):
        load_schema("service: [unclosed")
