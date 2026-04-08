"""Pydantic models describing a feathers service YAML schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
        return self


class ObservabilityDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metrics: Literal["prometheus", "none"] = "prometheus"
    tracing: Literal["otel", "none"] = "otel"
    logging: Literal["structlog", "stdlib"] = "structlog"


class DeployDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target: Literal["render", "fly", "docker"] = "render"
    min_instances: int = 0
    health: str = "/health"


class ServiceMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    python: str = "3.12"


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
