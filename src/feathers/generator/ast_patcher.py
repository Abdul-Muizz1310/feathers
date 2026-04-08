"""Incremental codegen — adds endpoints and models to an existing service.

Uses a marker-based splicing approach for v0.1.0: the generated router files
contain ``# feathers: begin endpoints`` / ``# feathers: end endpoints`` markers,
and new endpoint functions are inserted between them. Hand-written code between
``# feathers: begin hand-written`` / ``# feathers: end hand-written`` markers is
never touched.

A full libcst-based rewrite is deferred to v0.2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from feathers.generator.context import build_context
from feathers.schema import ServiceSchema

ActionTuple = tuple[Path, str]


class PatcherError(RuntimeError):
    """Raised when an incremental patch cannot be applied."""


@dataclass(frozen=True)
class _HandlerSite:
    router_file: Path
    func_name: str
    method: str
    path_suffix: str
    full_path: str
    handler: str


def add_endpoint(*, service_dir: Path, schema: ServiceSchema) -> list[ActionTuple]:
    """Add missing endpoint functions to the generated routers.

    Idempotent: re-running with the same schema is a no-op.
    """
    if not service_dir.is_dir():
        raise PatcherError(f"service dir not found: {service_dir}")

    ctx = build_context(schema)
    service_snake = ctx["service"]["snake"]
    routers_dir = service_dir / "src" / service_snake / "api" / "routers"
    if not routers_dir.is_dir():
        raise PatcherError(f"routers dir not found: {routers_dir}")

    actions: list[ActionTuple] = []
    for model in ctx["models"]:
        router_path = routers_dir / f"{model.plural_snake}.py"
        if not router_path.exists():
            continue

        wanted = [ep for ep in ctx["endpoints"] if ep.handler.startswith(f"{model.plural_snake}.")]
        for ep in wanted:
            if _has_function(router_path, ep.func_name):
                actions.append((router_path, "unchanged"))
            else:
                _append_endpoint_function(router_path, model.plural_snake, ep)
                actions.append((router_path, "added"))
    return actions


def add_model(*, service_dir: Path, schema: ServiceSchema) -> list[ActionTuple]:
    """Create model files for every model that does not already have one."""
    if not service_dir.is_dir():
        raise PatcherError(f"service dir not found: {service_dir}")

    ctx = build_context(schema)
    service_snake = ctx["service"]["snake"]
    models_dir = service_dir / "src" / service_snake / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    actions: list[ActionTuple] = []
    for model in ctx["models"]:
        model_file = models_dir / f"{model.snake}.py"
        if model_file.exists():
            actions.append((model_file, "unchanged"))
            continue
        model_file.write_text(
            f'"""{model.name} domain model (stub)."""\n\n'
            f"from dataclasses import dataclass\n\n\n"
            f"@dataclass\n"
            f"class {model.name}:\n"
            f"    id: str\n",
            encoding="utf-8",
        )
        actions.append((model_file, "added"))
    return actions


# ── Helpers ─────────────────────────────────────────────────────────────────

_FENCE_BEGIN = "# feathers: begin hand-written"
_FENCE_END = "# feathers: end hand-written"


def _has_function(path: Path, func_name: str) -> bool:
    text = path.read_text(encoding="utf-8")
    return re.search(rf"^async def {re.escape(func_name)}\b", text, re.MULTILINE) is not None


def _append_endpoint_function(path: Path, plural_snake: str, ep: object) -> None:
    """Append a new endpoint function to a router file without touching fences."""
    text = path.read_text(encoding="utf-8")

    method = ep.method  # type: ignore[attr-defined]
    http_path = ep.path  # type: ignore[attr-defined]
    handler = ep.handler  # type: ignore[attr-defined]
    func_name = endpoint_func_name_obj(ep)

    path_suffix = http_path.replace(f"/{plural_snake}", "", 1) or "/"
    snippet = (
        f'\n\n@router.{method.lower()}("{path_suffix}")\n'
        f"async def {func_name}() -> dict[str, str]:\n"
        f'    """{method} {http_path}"""\n'
        f'    return {{"handler": "{handler}"}}\n'
    )

    # Insert before any hand-written fence block if present; otherwise append.
    if _FENCE_BEGIN in text:
        idx = text.index(_FENCE_BEGIN)
        new_text = text[:idx].rstrip() + snippet + "\n\n" + text[idx:]
    else:
        new_text = text.rstrip() + snippet

    path.write_text(new_text, encoding="utf-8", newline="\n")


def endpoint_func_name_obj(ep: object) -> str:
    handler: str = ep.handler  # type: ignore[attr-defined]
    return handler.replace(".", "_")
