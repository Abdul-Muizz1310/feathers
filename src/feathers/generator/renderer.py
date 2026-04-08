"""Render a feathers service tree from Jinja2 templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    select_autoescape,
)

from feathers.generator.context import build_context
from feathers.schema import ServiceSchema

TEMPLATE_ROOT: Path = Path(__file__).resolve().parent.parent / "templates" / "service"


class RendererError(RuntimeError):
    """Raised when the service tree cannot be rendered."""


@dataclass(frozen=True)
class TemplateTarget:
    template: str
    output: str
    per_model: bool = False


# Manifest of templates to render. `output` may reference {{service_snake}} and,
# for per-model templates, {{model_snake}} / {{model_plural_snake}}.
_MANIFEST: tuple[TemplateTarget, ...] = (
    # Top-level project files
    TemplateTarget("pyproject.toml.j2", "pyproject.toml"),
    TemplateTarget("README.md.j2", "README.md"),
    TemplateTarget("Makefile.j2", "Makefile"),
    TemplateTarget("Dockerfile.j2", "Dockerfile"),
    TemplateTarget("render.yaml.j2", "render.yaml"),
    TemplateTarget(".env.example.j2", ".env.example"),
    TemplateTarget(".gitignore.j2", ".gitignore"),
    TemplateTarget(".python-version.j2", ".python-version"),
    TemplateTarget("ci.yml.j2", ".github/workflows/ci.yml"),
    # Package source
    TemplateTarget("src/__init__.py.j2", "src/{{service_snake}}/__init__.py"),
    TemplateTarget("src/main.py.j2", "src/{{service_snake}}/main.py"),
    TemplateTarget("src/core/__init__.py.j2", "src/{{service_snake}}/core/__init__.py"),
    TemplateTarget("src/core/config.py.j2", "src/{{service_snake}}/core/config.py"),
    TemplateTarget("src/core/platform.py.j2", "src/{{service_snake}}/core/platform.py"),
    TemplateTarget("src/api/__init__.py.j2", "src/{{service_snake}}/api/__init__.py"),
    TemplateTarget(
        "src/api/routers/__init__.py.j2",
        "src/{{service_snake}}/api/routers/__init__.py",
    ),
    # Per-model router
    TemplateTarget(
        "src/api/routers/router.py.j2",
        "src/{{service_snake}}/api/routers/{{model_plural_snake}}.py",
        per_model=True,
    ),
    TemplateTarget("src/models/__init__.py.j2", "src/{{service_snake}}/models/__init__.py"),
    TemplateTarget(
        "src/models/model.py.j2",
        "src/{{service_snake}}/models/{{model_snake}}.py",
        per_model=True,
    ),
    # Tests (placeholder)
    TemplateTarget("tests/__init__.py.j2", "tests/__init__.py"),
    TemplateTarget("tests/test_health.py.j2", "tests/test_health.py"),
)


def render_service(schema: ServiceSchema, *, out_dir: Path, force: bool = False) -> list[Path]:
    """Render a service into ``out_dir / schema.service.name``."""
    if not TEMPLATE_ROOT.is_dir():
        raise RendererError(f"template root missing: {TEMPLATE_ROOT}")

    ctx = build_context(schema)
    service_snake: str = ctx["service"]["snake"]
    target = (out_dir / service_snake).resolve()

    if target.exists() and not force:
        raise FileExistsError(f"target already exists: {target}")
    target.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)),
        autoescape=select_autoescape(enabled_extensions=()),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )

    written: list[Path] = []
    for item in _MANIFEST:
        if item.per_model:
            for model in ctx["models"]:
                written.append(
                    _render_one(
                        env,
                        item,
                        ctx={
                            **ctx,
                            "model": model,
                            "model_snake": model.snake,
                            "model_plural_snake": model.plural_snake,
                        },
                        target=target,
                        service_snake=service_snake,
                    )
                )
        else:
            written.append(
                _render_one(env, item, ctx=ctx, target=target, service_snake=service_snake)
            )

    return sorted(written)


def _render_one(
    env: Environment,
    item: TemplateTarget,
    *,
    ctx: dict[str, Any],
    target: Path,
    service_snake: str,
) -> Path:
    try:
        tmpl = env.get_template(item.template)
    except TemplateError as exc:
        raise RendererError(f"template load failed: {item.template}: {exc}") from exc

    try:
        body = tmpl.render(**ctx)
    except TemplateError as exc:
        raise RendererError(f"template render failed: {item.template}: {exc}") from exc

    out_path = _render_path(
        item.output,
        service_snake=service_snake,
        model_snake=ctx.get("model_snake"),
        model_plural_snake=ctx.get("model_plural_snake"),
    )
    dest = target / out_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8", newline="\n")
    return dest.resolve()


def _render_path(
    template: str,
    *,
    service_snake: str,
    model_snake: str | None,
    model_plural_snake: str | None,
) -> str:
    out = template.replace("{{service_snake}}", service_snake)
    if model_snake is not None:
        out = out.replace("{{model_snake}}", model_snake)
    if model_plural_snake is not None:
        out = out.replace("{{model_plural_snake}}", model_plural_snake)
    return out
