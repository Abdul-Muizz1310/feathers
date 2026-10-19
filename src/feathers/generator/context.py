"""Build a Jinja render context from a validated ServiceSchema."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from feathers.generator import codegen
from feathers.generator.codegen import FieldView
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


#: The CRUD verbs the router template knows how to emit for a model.
CRUD_ACTIONS: tuple[str, ...] = ("create", "get", "list", "update", "delete")

_PATH_PARAM = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


@dataclass(frozen=True)
class EndpointView:
    method: str
    path: str
    handler: str
    auth: str
    paginate: str
    func_name: str
    action: str
    #: The path relative to the model router's ``/<plural>`` prefix.
    route_path: str
    #: The mounted path with every ``{param}`` renamed ``{item_id}`` (for f-strings).
    url_template: str


@dataclass(frozen=True)
class ModelView:
    name: str
    snake: str
    plural_snake: str
    fields: list[FieldDef]
    soft_delete: bool
    audit: bool
    #: True when a ``list`` endpoint of this model uses offset (or ``none``) paging.
    offset_list: bool = False
    #: True when a ``list`` endpoint of this model uses keyset (``cursor``) paging.
    cursor_list: bool = False
    #: The first endpoint per CRUD verb that this model's router renders.
    crud: dict[str, EndpointView] = field(default_factory=dict)

    @property
    def py_fields(self) -> list[FieldView]:
        out: list[FieldView] = []
        for f in self.fields:
            entry: FieldView = {
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
                # Rendered source fragments (filled in below, then consumed by
                # the templates); seeded so the TypedDict is complete.
                "annotation": "",
                "sa_column": "",
                "pydantic_type": "",
                "sample": "",
                "sample_expr": "",
                "default_literal": None,
                "column": "",
            }
            entry["annotation"] = codegen.annotation(entry)
            entry["sa_column"] = codegen.sa_column(entry)
            entry["pydantic_type"] = codegen.pydantic_type(entry)
            entry["sample"] = codegen.sample_literal(entry)
            entry["sample_expr"] = codegen.sample_expr(entry)
            entry["column"] = codegen.column(entry)
            entry["default_literal"] = (
                None if f.default is None else codegen.python_literal(f.default)
            )
            out.append(entry)
        return out

    @property
    def pk(self) -> FieldView:
        """The primary-key field (first ``primary`` field, else the first field)."""
        for f in self.py_fields:
            if f["primary"]:
                return f
        return self.py_fields[0]

    @property
    def seeded_sample(self) -> bool:
        """True when a generated create body needs a per-request ``seed``."""
        return any("seed" in f["sample_expr"] for f in self.create_fields)

    @property
    def create_fields(self) -> list[FieldView]:
        """Fields a client supplies on create (no PK, no auto-timestamps)."""
        return codegen.create_fields(self)

    @property
    def model_imports(self) -> list[str]:
        """Minimal import lines for the model module."""
        return codegen.model_imports(self)

    @property
    def schema_imports(self) -> list[str]:
        """Minimal import lines for the Pydantic schema module."""
        return codegen.schema_imports(self)


def endpoint_func_name(ep: EndpointDef) -> str:
    return ep.handler.replace(".", "_")


def service_id(name: str) -> str:
    """The platform-token audience for a service: its snake name in kebab case."""
    return snake(name).replace("_", "-")


def build_context(schema: ServiceSchema) -> dict[str, Any]:
    service_name = schema.service.name
    endpoints = [_to_endpoint_view(e) for e in schema.endpoints]
    models = [_to_model_view(m, endpoints) for m in schema.models]
    routed = {m.plural_snake for m in models}
    primary_model = models[0]
    return {
        "service": {
            "name": service_name,
            "snake": snake(service_name),
            "id": service_id(service_name),
            "description": schema.service.description,
            "python": schema.service.python,
            "copyright": schema.service.copyright,
        },
        "models": models,
        "endpoints": endpoints,
        "primary_model": primary_model,
        # (method, anchored regex) of every rendered `auth: none` route: public by design.
        "public_endpoints": [
            (e.method, _route_regex(e.url_template))
            for e in endpoints
            if e.auth == "none" and _resource(e.handler) in routed
        ],
        "observability": schema.observability.model_dump(),
        "deploy": schema.deploy.model_dump(),
    }


def _to_model_view(m: ModelDef, endpoints: list[EndpointView]) -> ModelView:
    plural_snake = plural(snake(m.name))
    own = [e for e in endpoints if _resource(e.handler) == plural_snake]
    lists = [e for e in own if e.action == "list"]
    crud: dict[str, EndpointView] = {}
    for e in own:
        if e.action in CRUD_ACTIONS:
            crud.setdefault(e.action, e)
    return ModelView(
        name=m.name,
        snake=snake(m.name),
        plural_snake=plural_snake,
        fields=list(m.fields),
        soft_delete=m.soft_delete,
        audit=m.audit,
        offset_list=any(e.paginate != "cursor" for e in lists),
        cursor_list=any(e.paginate == "cursor" for e in lists),
        crud=crud,
    )


def _resource(handler: str) -> str:
    """The router a handler belongs to — the part before the dot in "<resource>.<action>"."""
    return handler.split(".")[0]


def _to_endpoint_view(e: EndpointDef) -> EndpointView:
    resource = _resource(e.handler)
    # Same rule the router template applies: drop the resource segment, mount on it.
    route_path = e.path.replace(f"/{resource}", "")
    return EndpointView(
        method=e.method,
        path=e.path,
        handler=e.handler,
        auth=e.auth,
        paginate=e.paginate,
        func_name=endpoint_func_name(e),
        # The CRUD verb — the part after the dot in "<resource>.<action>".
        action=e.handler.split(".")[-1],
        route_path=route_path,
        url_template=_PATH_PARAM.sub("{item_id}", f"/{resource}{route_path}"),
    )


def _route_regex(url_template: str) -> str:
    """An anchored regex matching a mounted path, any ``{param}`` one segment."""
    segments = url_template.split("/")
    parts = ["[^/]+" if s == "{item_id}" else re.escape(s) for s in segments]
    return "^" + "/".join(parts) + "$"
