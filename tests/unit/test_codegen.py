"""Unit tests for feathers.generator.codegen — the type-sensitive code rendering.

These cover the full field-type matrix (the demo only uses a slice), so the
generated SQLAlchemy columns, Pydantic types, and import sets are verified
without having to boot a service for every type.
"""

from __future__ import annotations

from feathers.generator import codegen
from feathers.generator.context import build_context
from feathers.schema import load_schema

ALL_TYPES_YAML = """\
service:
  name: gallery
  description: all field types
models:
  - name: Asset
    soft_delete: true
    audit: true
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: title, type: str, max_length: 120, unique: true, indexed: true }
      - { name: body, type: text }
      - { name: views, type: int, default: 0 }
      - { name: ratio, type: float }
      - { name: featured, type: bool, default: false }
      - { name: kind, type: enum, values: [photo, video], default: photo }
      - { name: meta, type: json, nullable: true }
      - { name: created_at, type: datetime, default: now }
  - name: Tag
    fields:
      - { name: label, type: str, max_length: 40 }
endpoints:
  - { method: GET, path: "/assets/{id}", handler: assets.get }
"""


def _models() -> dict:
    ctx = build_context(load_schema(ALL_TYPES_YAML))
    return {m.name: m for m in ctx["models"]}


def _field(model, name: str) -> dict:
    return next(f for f in model.py_fields if f["name"] == name)


# ── python_literal ───────────────────────────────────────────────────────────


def test_python_literal_bool() -> None:
    assert codegen.python_literal(True) == "True"
    assert codegen.python_literal(False) == "False"


def test_python_literal_str_and_number() -> None:
    assert codegen.python_literal("viewer") == "'viewer'"
    assert codegen.python_literal(0) == "0"
    assert codegen.python_literal(1.5) == "1.5"


# ── sa_column ────────────────────────────────────────────────────────────────


def test_sa_column_uuid_primary() -> None:
    col = _field(_models()["Asset"], "id")["sa_column"]
    assert col == "mapped_column(Uuid(), primary_key=True, default=uuid4)"


def test_sa_column_string_with_constraints() -> None:
    col = _field(_models()["Asset"], "title")["sa_column"]
    assert col == "mapped_column(String(120), unique=True, index=True)"


def test_sa_column_nullable_json() -> None:
    col = _field(_models()["Asset"], "meta")["sa_column"]
    assert col == "mapped_column(JSON(), nullable=True)"


def test_sa_column_int_default() -> None:
    assert _field(_models()["Asset"], "views")["sa_column"] == "mapped_column(Integer(), default=0)"


def test_sa_column_bool_default() -> None:
    col = _field(_models()["Asset"], "featured")["sa_column"]
    assert col == "mapped_column(Boolean(), default=False)"


def test_sa_column_enum_is_string() -> None:
    col = _field(_models()["Asset"], "kind")["sa_column"]
    assert col == "mapped_column(String(), default='photo')"


def test_sa_column_auto_timestamp() -> None:
    col = _field(_models()["Asset"], "created_at")["sa_column"]
    assert col == "mapped_column(DateTime(timezone=True), server_default=func.now())"


def test_sa_column_plain_float() -> None:
    assert _field(_models()["Asset"], "ratio")["sa_column"] == "mapped_column(Float())"


INT_PK_YAML = """\
service:
  name: counters
models:
  - name: Counter
    fields:
      - { name: code, type: int, primary: true }
      - { name: label, type: str }
endpoints: []
"""


def _counter():
    ctx = build_context(load_schema(INT_PK_YAML))
    return {m.name: m for m in ctx["models"]}["Counter"]


def test_sa_column_non_uuid_primary_key() -> None:
    """A non-UUID primary key gets primary_key=True but no uuid4 default."""
    col = _field(_counter(), "code")["sa_column"]
    assert col == "mapped_column(Integer(), primary_key=True)"


def test_schema_imports_without_uuid() -> None:
    """A model with no UUID field must not import UUID in its schema module."""
    lines = codegen.schema_imports(_counter())
    assert not any("uuid" in line.lower() for line in lines)


# ── annotation / pydantic_type ───────────────────────────────────────────────


def test_annotation_nullable() -> None:
    assert _field(_models()["Asset"], "meta")["annotation"] == "dict[str, Any] | None"


def test_annotation_plain() -> None:
    assert _field(_models()["Asset"], "title")["annotation"] == "str"


def test_pydantic_type_enum_is_literal() -> None:
    assert _field(_models()["Asset"], "kind")["pydantic_type"] == "Literal['photo', 'video']"


def test_pydantic_type_plain() -> None:
    assert _field(_models()["Asset"], "views")["pydantic_type"] == "int"


# ── imports ──────────────────────────────────────────────────────────────────


def test_model_imports_cover_all_types() -> None:
    lines = codegen.model_imports(_models()["Asset"])
    assert "from datetime import datetime" in lines
    assert "from uuid import UUID, uuid4" in lines
    assert "from typing import Any" in lines
    sa_line = next(line for line in lines if line.startswith("from sqlalchemy import"))
    for name in ("Boolean", "DateTime", "Float", "Integer", "JSON", "String", "Uuid", "func"):
        assert name in sa_line


def test_schema_imports_cover_all_types() -> None:
    lines = codegen.schema_imports(_models()["Asset"])
    assert "from datetime import datetime" in lines
    assert "from typing import Literal" in lines
    assert "from typing import Any" in lines
    assert "from uuid import UUID" in lines


def test_model_imports_minimal_for_simple_model() -> None:
    # Tag has only a str field — no datetime/uuid/typing imports.
    lines = codegen.model_imports(_models()["Tag"])
    assert not any("datetime" in line for line in lines)
    assert not any("uuid" in line for line in lines)
    sa_line = next(line for line in lines if line.startswith("from sqlalchemy import"))
    assert "String" in sa_line


# ── pk / create_fields / sample ──────────────────────────────────────────────


def test_pk_prefers_primary() -> None:
    assert _models()["Asset"].pk["name"] == "id"


def test_pk_falls_back_to_first_field() -> None:
    # Tag declares no primary field → first field is used.
    assert _models()["Tag"].pk["name"] == "label"


def test_create_fields_excludes_pk_and_auto_timestamp() -> None:
    names = [f["name"] for f in _models()["Asset"].create_fields]
    assert "id" not in names
    assert "created_at" not in names
    assert {"title", "body", "views", "ratio", "featured", "kind", "meta"} <= set(names)


def test_sample_literal_by_type() -> None:
    asset = _models()["Asset"]
    assert _field(asset, "title")["sample"] == '"example"'
    assert _field(asset, "views")["sample"] == "1"
    assert _field(asset, "ratio")["sample"] == "1.0"
    assert _field(asset, "featured")["sample"] == "True"
    assert _field(asset, "meta")["sample"] == "{}"
    assert _field(asset, "created_at")["sample"] == '"2026-01-01T00:00:00Z"'
    assert _field(asset, "id")["sample"] == '"00000000-0000-0000-0000-000000000001"'
    # Enum sample uses the first declared value.
    assert _field(asset, "kind")["sample"] == "'photo'"
