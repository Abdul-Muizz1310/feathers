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
    sample_expr: str
    default_literal: str | None
    column: str


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


#: The generated project's ruff line length (pyproject.toml.j2 `[tool.ruff]`).
LINE_LENGTH = 100


def python_literal(value: str | int | float | bool | None) -> str:
    """Render a default value as a Python literal, quoted the way `ruff format` wants.

    Double quotes unless the value itself contains a double quote (and no single
    quote), in which case ``repr``'s single-quoted form has fewer escapes.
    """
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        literal = repr(value)
        if literal.startswith("'") and '"' not in value:
            literal = '"' + literal[1:-1] + '"'
        return literal
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


def column(field: FieldView) -> str:
    """The whole ``name: Mapped[...] = mapped_column(...)`` statement, indented.

    One line when it fits in :data:`LINE_LENGTH`; otherwise one argument per line
    with a magic trailing comma, which `ruff format` leaves exactly as written.
    """
    head = f"    {field['name']}: Mapped[{field['annotation']}] = "
    one_line = head + field["sa_column"]
    if len(one_line) <= LINE_LENGTH:
        return one_line
    args = _split_top_level(field["sa_column"].removeprefix("mapped_column(")[:-1])
    body = "".join(f"        {arg},\n" for arg in args)
    return f"{head}mapped_column(\n{body}    )"


def _split_top_level(args: str) -> list[str]:
    """Split a call's argument source on commas that are not inside brackets."""
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(args):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
    parts.append(args[start:].strip())
    return parts


def pydantic_type(field: FieldView) -> str:
    """The Pydantic field type — a ``Literal`` for enums, else the Python type."""
    if field["values"]:
        members = ", ".join(python_literal(v) for v in field["values"])
        return f"Literal[{members}]"
    return str(field["py_type"])


def isort_names(names: set[str]) -> list[str]:
    """Order imported names the way isort (and ruff's ``I`` rules) do.

    Constants (all caps) first, then classes (capitalised), then everything else;
    case-insensitively within each group.
    """

    def key(name: str) -> tuple[int, str, str]:
        kind = 0 if name.isupper() and len(name) > 1 else 1 if name[:1].isupper() else 2
        return kind, name.lower(), name

    return sorted(names, key=key)


def model_imports(model: ModelView) -> list[str]:
    """Minimal import lines for a model module: stdlib, a blank line, SQLAlchemy."""
    fields = model.py_fields
    py_types = {f["py_type"] for f in fields}
    needs_dt = "datetime" in py_types or model.audit or model.soft_delete
    needs_func = model.audit or any(is_auto_timestamp(f) for f in fields)

    stdlib: list[str] = []
    if needs_dt:
        stdlib.append("from datetime import datetime")
    if "UUID" in py_types:
        stdlib.append("from uuid import UUID, uuid4")
    if "dict[str, Any]" in py_types:
        stdlib.append("from typing import Any")

    sa_names = {_SA_IMPORT[f["sa_type"]] for f in fields}
    if needs_dt:
        sa_names.add("DateTime")
    if needs_func:
        sa_names.add("func")
    sa_line = "from sqlalchemy import " + ", ".join(isort_names(sa_names))

    return [*sorted(stdlib), "", sa_line] if stdlib else [sa_line]


def schema_imports(model: ModelView) -> list[str]:
    """Minimal stdlib import lines for a Pydantic schema module (one per module)."""
    fields = model.py_fields
    py_types = {f["py_type"] for f in fields}

    lines: list[str] = []
    if "datetime" in py_types or model.audit or model.soft_delete:
        lines.append("from datetime import datetime")
    typing_names: set[str] = set()
    if any(f["values"] for f in fields):
        typing_names.add("Literal")
    if "dict[str, Any]" in py_types:
        typing_names.add("Any")
    if typing_names:
        lines.append("from typing import " + ", ".join(isort_names(typing_names)))
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
        return python_literal(field["values"][0])
    return _SAMPLE_BY_TYPE[field["py_type"]]


#: Sample expressions for unique columns, over a per-request ``seed`` (8 hex chars),
#: so a generated test can create several rows in one database without collisions.
_SEEDED_SAMPLE_BY_TYPE: dict[str, str] = {
    "str": 'f"x{seed}"',
    "int": "int(seed, 16)",
}


def sample_expr(field: FieldView) -> str:
    """A sample *expression* for a generated create body (seeded when unique)."""
    if field["unique"] and not field["values"] and field["py_type"] in _SEEDED_SAMPLE_BY_TYPE:
        return _SEEDED_SAMPLE_BY_TYPE[field["py_type"]]
    return sample_literal(field)
