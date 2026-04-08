"""Public error type for schema validation."""

from __future__ import annotations

from pathlib import Path


class SchemaError(ValueError):
    """Raised when a user-supplied YAML schema is invalid.

    All parsing and validation failures raised at the public surface of
    :mod:`feathers.schema` are instances of this error.
    """

    def __init__(self, message: str, *, source: Path | None = None) -> None:
        self.message = message
        self.source = source
        full = f"{message} (in {source})" if source is not None else message
        super().__init__(full)
