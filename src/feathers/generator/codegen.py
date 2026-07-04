"""Render schema fields into SQLAlchemy + Pydantic source fragments.

The renderer templates stay declarative by delegating the type-sensitive parts
of code generation here, where the logic is unit-tested. Each function takes a
:class:`FieldView` (produced by :meth:`~feathers.generator.context.ModelView.py_fields`)
and returns a Python source fragment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from feathers.generator.context import ModelView


class FieldView(TypedDict):
    """The fully-resolved view of a single model field shared with the templates.

    Produced by :meth:`~feathers.generator.context.ModelView.py_fields`; the
    typed contract between ``context`` and ``codegen``/the Jinja templates,
    replacing the previous ``dict[str, Any]``.
    """

    name: str
    py_type: str
    sa_type: str
    primary: bool
    unique: bool
    indexed: bool
    nullable: bool
    max_length: int | None
    values: list[str] | None
    default: str | int | float | bool | None
    annotation: str
    sa_column: str
    pydantic_type: str
    sample: str
    default_literal: str | None


# SQLAlchemy 2.0 column type constructors keyed by the schema's SA type name.
_SA_CONSTRUCTOR: dict[str, str] = {
    "UUID": "Uuid()",
    "Text": "Text()",
    "Integer": "Integer()",
    "Float": "Float()",
    "Boolean": "Boolean()",
    "DateTime": "DateTime(timezone=True)",
    "JSON": "JSON()",
    # Enums are stored as strings; the Pydantic Literal enforces the value set.
    "Enum": "String()",
}

# Importable SQLAlchemy names per SA type (for a minimal, lint-clean import set).
_SA_IMPORT: dict[str, str] = {
    "UUID": "Uuid",
    "String": "String",
    "Text": "Text",
    "Integer": "Integer",
    "Float": "Float",
    "Boolean": "Boolean",
    "DateTime": "DateTime",
    "JSON": "JSON",
    "Enum": "String",
}


def python_literal(value: str | int | float | bool | None) -> str:
    """Render a default value as a Python literal."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return repr(value)
    return str(value)


def is_auto_timestamp(field: FieldView) -> bool:
    """True for a datetime field defaulting to the current time."""
    return bool(field["py_type"] == "datetime" and field["default"] == "now")


def annotation(field: FieldView) -> str:
    """The ``Mapped[...]`` inner type for a field."""
    inner: str = field["py_type"]
    if field["nullable"]:
        inner = f"{inner} | None"
    return inner


def sa_column(field: FieldView) -> str:
    """The ``mapped_column(...)`` expression for a field."""
    sa = field["sa_type"]
    if sa == "String":
        type_expr = f"String({field['max_length']})" if field["max_length"] else "String()"
    else:
        type_expr = _SA_CONSTRUCTOR[sa]

    parts: list[str] = [type_expr]
    if field["primary"]:
        parts.append("primary_key=True")
        if sa == "UUID":
            parts.append("default=uuid4")
    if field["unique"]:
        parts.append("unique=True")
    if field["indexed"]:
        parts.append("index=True")
    if field["nullable"]:
        parts.append("nullable=True")

    if is_auto_timestamp(field):
        parts.append("server_default=func.now()")
    elif field["default"] is not None and not field["primary"]:
        parts.append(f"default={python_literal(field['default'])}")

    return "mapped_column(" + ", ".join(parts) + ")"


def pydantic_type(field: FieldView) -> str:
    """The Pydantic field type — a ``Literal`` for enums, else the Python type."""
    if field["values"]:
        members = ", ".join(repr(v) for v in field["values"])
        return f"Literal[{members}]"
    return str(field["py_type"])


def model_imports(model: ModelView) -> list[str]:
    """Sorted, minimal import lines for a model module."""
    fields = model.py_fields
    py_types = {f["py_type"] for f in fields}
    needs_dt = "datetime" in py_types or model.audit or model.soft_delete

    stdlib: list[str] = []
    if "datetime" in py_types or needs_dt:
        stdlib.append("from datetime import datetime")
    if "UUID" in py_types:
        stdlib.append("from uuid import UUID, uuid4")
    if "dict[str, Any]" in py_types:
        stdlib.append("from typing import Any")

    sa_names = {_SA_IMPORT[f["sa_type"]] for f in fields}
    if needs_dt:
        sa_names.add("DateTime")
    sa_names.add("func")
    sa_line = "from sqlalchemy import " + ", ".join(sorted(sa_names))

    return [*sorted(stdlib), sa_line]


def schema_imports(model: ModelView) -> list[str]:
    """Sorted, minimal import lines for a Pydantic schema module."""
    fields = model.py_fields
    py_types = {f["py_type"] for f in fields}

    lines: list[str] = []
    if "datetime" in py_types:
        lines.append("from datetime import datetime")
    typing_names: list[str] = []
    if any(f["values"] for f in fields):
        typing_names.append("Literal")
    if typing_names:
        lines.append("from typing import " + ", ".join(typing_names))
    if "dict[str, Any]" in py_types:
        lines.append("from typing import Any")
    if "UUID" in py_types:
        lines.append("from uuid import UUID")
    return sorted(lines)


def create_fields(model: ModelView) -> list[FieldView]:
    """Fields a client supplies on create: not the primary key, not auto-timestamps."""
    return [f for f in model.py_fields if not f["primary"] and not is_auto_timestamp(f)]


_SAMPLE_BY_TYPE: dict[str, str] = {
    "str": '"example"',
    "int": "1",
    "float": "1.0",
    "bool": "True",
    "datetime": '"2026-01-01T00:00:00Z"',
    "UUID": '"00000000-0000-0000-0000-000000000001"',
    "dict[str, Any]": "{}",
}


def sample_literal(field: FieldView) -> str:
    """A representative Python literal for a field, for generated test bodies."""
    if field["values"]:
        return repr(field["values"][0])
    return _SAMPLE_BY_TYPE[field["py_type"]]
