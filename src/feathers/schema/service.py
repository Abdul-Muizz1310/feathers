"""Pydantic models describing a feathers service YAML schema."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# A service name becomes the Python package (snake_case) and the platform-token
# audience (kebab-case), so it must be an identifier that maps cleanly onto both.
_SERVICE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
# Endpoint paths are embedded in generated string literals and route regexes: allow
# only plain URL segments and `{identifier}` parameters, nothing that needs escaping.
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9._~-]+|\{[A-Za-z_][A-Za-z0-9_]*\}")

FieldType = Literal["uuid", "str", "int", "float", "bool", "datetime", "enum", "json", "text"]
HttpMethod = Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
AuthRole = Literal["none", "any", "admin", "editor", "viewer"]


class FieldDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: FieldType
    primary: bool = False
    unique: bool = False
    indexed: bool = False
    nullable: bool = False
    default: str | int | float | bool | None = None
    values: list[str] | None = None
    max_length: int | None = None

    @model_validator(mode="after")
    def _enum_needs_values(self) -> FieldDef:
        if self.type == "enum" and not self.values:
            raise ValueError(f"enum field '{self.name}' must declare `values`")
        return self


class ModelDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: list[FieldDef]
    soft_delete: bool = False
    audit: bool = False
    table_name: str | None = None

    @model_validator(mode="after")
    def _unique_field_names(self) -> ModelDef:
        seen: set[str] = set()
        for f in self.fields:
            if f.name in seen:
                raise ValueError(f"duplicate field name '{f.name}' in model {self.name}")
            seen.add(f.name)
        return self


class EndpointDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: HttpMethod
    path: str
    handler: str
    auth: AuthRole = "any"
    paginate: Literal["none", "offset", "cursor"] = "none"

    @model_validator(mode="after")
    def _path_leading_slash(self) -> EndpointDef:
        if not self.path.startswith("/"):
            raise ValueError(f"endpoint path must start with '/': {self.path!r}")
        if self.path != "/" and not all(
            _PATH_SEGMENT.fullmatch(segment) for segment in self.path[1:].split("/")
        ):
            raise ValueError(
                f"endpoint path segments must be plain (A-Z a-z 0-9 . _ ~ -) or a"
                f" {{parameter}}: {self.path!r}"
            )
        return self


class ObservabilityDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Only options the generator actually consumes are exposed. `metrics`
    # gates the Prometheus instrumentator + its dependency; `logging` gates
    # structlog configuration + its dependency. There is no `tracing` option:
    # OpenTelemetry is not wired into the generated service and is not a
    # dependency, so exposing it would be inert config (see audit OPT-1).
    # `extra="forbid"` makes a stray `tracing:` key fail loudly rather than
    # silently do nothing.
    metrics: Literal["prometheus", "none"] = "prometheus"
    logging: Literal["structlog", "stdlib"] = "structlog"


class DeployDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # The generator emits exactly one deploy target: a Render blueprint
    # (render.yaml) backed by the generated Dockerfile. There is no `target`
    # switch because no template branches on it — a `render`/`fly`/`docker`
    # field would be inert config (see audit OPT-1). `extra="forbid"` rejects a
    # stray `target:` key instead of silently ignoring it.
    health: str = "/health"


class ServiceMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    python: str = "3.12"
    # The generated LICENSE's "Copyright (c) <copyright>" line. A schema field rather
    # than the current date, so regeneration stays byte-identical.
    copyright: str = Field(default="2026 Abdul-Muizz Anwar", min_length=1)

    @field_validator("name")
    @classmethod
    def _name_is_an_identifier(cls, value: str) -> str:
        if not _SERVICE_NAME.fullmatch(value):
            raise ValueError(
                f"service name must start with a letter and contain only letters, digits"
                f" and underscores (it becomes the package and the service id): {value!r}"
            )
        return value


class ServiceSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service: ServiceMeta
    models: list[ModelDef] = Field(default_factory=list)
    endpoints: list[EndpointDef] = Field(default_factory=list)
    observability: ObservabilityDef = Field(default_factory=ObservabilityDef)
    deploy: DeployDef = Field(default_factory=DeployDef)

    @model_validator(mode="after")
    def _at_least_one_model(self) -> ServiceSchema:
        if not self.models:
            raise ValueError("a service must declare at least one model")
        return self
