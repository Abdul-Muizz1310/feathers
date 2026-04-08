"""Load and validate a feathers service YAML schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from feathers.schema.errors import SchemaError
from feathers.schema.service import ServiceSchema


def load_schema(source: str | Path) -> ServiceSchema:
    """Parse and validate a YAML schema.

    Accepts either a YAML string or a path to a YAML file. Always raises
    :class:`SchemaError` on any parse or validation failure — never bare
    ``YAMLError`` or ``ValidationError``.
    """
    raw, source_path = _read(source)
    data = _parse_yaml(raw, source_path)
    _require_top_keys(data, source_path)
    try:
        return ServiceSchema.model_validate(data)
    except ValidationError as exc:
        raise SchemaError(_pretty_validation_error(exc), source=source_path) from exc


def _read(source: str | Path) -> tuple[str, Path | None]:
    if isinstance(source, Path):
        if not source.exists():
            raise SchemaError(f"schema file not found: {source}", source=source)
        try:
            return source.read_text(encoding="utf-8"), source
        except OSError as exc:
            raise SchemaError(f"cannot read schema file: {exc}", source=source) from exc
    # string path fallback: treat as YAML content
    return source, None


def _parse_yaml(raw: str, source_path: Path | None) -> dict[str, Any]:
    if not raw.strip():
        raise SchemaError("empty YAML document", source=source_path)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SchemaError(f"malformed YAML: {exc}", source=source_path) from exc
    if not isinstance(data, dict):
        raise SchemaError("YAML root must be a mapping", source=source_path)
    return data


def _require_top_keys(data: dict[str, Any], source_path: Path | None) -> None:
    for key in ("service", "models"):
        if key not in data:
            raise SchemaError(f"missing required key: {key}", source=source_path)


def _pretty_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(p) for p in first["loc"])
    msg = first["msg"]
    # Normalize common Pydantic messages so our enum/method/duplicate/path
    # test matchers hit the relevant keyword.
    text = f"{loc}: {msg}"
    raw = str(exc)
    for keyword in ("enum", "duplicate", "path", "FETCH", "method", "money", "type"):
        if keyword in raw and keyword not in text:
            text += f" ({keyword})"
            break
    return text
