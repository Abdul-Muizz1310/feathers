"""Pydantic schema for the feathers service YAML."""

from __future__ import annotations

from feathers.schema.errors import SchemaError
from feathers.schema.loader import load_schema
from feathers.schema.service import (
    DeployDef,
    EndpointDef,
    FieldDef,
    ModelDef,
    ObservabilityDef,
    ServiceMeta,
    ServiceSchema,
)

__all__ = [
    "DeployDef",
    "EndpointDef",
    "FieldDef",
    "ModelDef",
    "ObservabilityDef",
    "SchemaError",
    "ServiceMeta",
    "ServiceSchema",
    "load_schema",
]
