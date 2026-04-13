"""Build a Jinja render context from a validated ServiceSchema."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from feathers.schema import EndpointDef, FieldDef, ModelDef, ServiceSchema

_SA_TYPES: dict[str, str] = {
    "uuid": "UUID",
    "str": "String",
    "text": "Text",
    "int": "Integer",
    "float": "Float",
    "bool": "Boolean",
    "datetime": "DateTime",
    "enum": "Enum",
    "json": "JSON",
}

_PY_TYPES: dict[str, str] = {
    "uuid": "UUID",
    "str": "str",
    "text": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "datetime": "datetime",
    "enum": "str",
    "json": "dict[str, Any]",
}


def snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


def plural(name: str) -> str:
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"


@dataclass(frozen=True)
class ModelView:
    name: str
    snake: str
    plural_snake: str
    fields: list[FieldDef]
    soft_delete: bool
    audit: bool

    @property
    def py_fields(self) -> list[dict[str, Any]]:
        out = []
        for f in self.fields:
            out.append(
                {
                    "name": f.name,
                    "py_type": _PY_TYPES[f.type],
                    "sa_type": _SA_TYPES[f.type],
                    "primary": f.primary,
                    "unique": f.unique,
                    "indexed": f.indexed,
                    "nullable": f.nullable,
                    "max_length": f.max_length,
                    "values": f.values,
                    "default": f.default,
                }
            )
        return out


@dataclass(frozen=True)
class EndpointView:
    method: str
    path: str
    handler: str
    auth: str
    paginate: str
    func_name: str


def endpoint_func_name(ep: EndpointDef) -> str:
    return ep.handler.replace(".", "_")


def build_context(schema: ServiceSchema) -> dict[str, Any]:
    service_name = schema.service.name
    models = [_to_model_view(m) for m in schema.models]
    endpoints = [_to_endpoint_view(e) for e in schema.endpoints]
    primary_model = models[0]
    return {
        "service": {
            "name": service_name,
            "snake": snake(service_name),
            "description": schema.service.description,
            "python": schema.service.python,
        },
        "models": models,
        "endpoints": endpoints,
        "primary_model": primary_model,
        "observability": schema.observability.model_dump(),
        "deploy": schema.deploy.model_dump(),
    }


def _to_model_view(m: ModelDef) -> ModelView:
    return ModelView(
        name=m.name,
        snake=snake(m.name),
        plural_snake=plural(snake(m.name)),
        fields=list(m.fields),
        soft_delete=m.soft_delete,
        audit=m.audit,
    )


def _to_endpoint_view(e: EndpointDef) -> EndpointView:
    return EndpointView(
        method=e.method,
        path=e.path,
        handler=e.handler,
        auth=e.auth,
        paginate=e.paginate,
        func_name=endpoint_func_name(e),
    )
