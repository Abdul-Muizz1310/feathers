"""Red tests for feathers.generator.renderer."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from feathers.generator import RendererError, render_service
from feathers.schema import load_schema


def _sha_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_renders_users_demo(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    written = render_service(schema, out_dir=tmp_path)
    target = tmp_path / "hello_users"
    assert target.is_dir()
    assert (target / "pyproject.toml").is_file()
    assert (target / "README.md").is_file()
    assert (target / "src" / "hello_users" / "main.py").is_file()
    assert (target / "src" / "hello_users" / "core" / "platform.py").is_file()
    assert (target / ".github" / "workflows" / "ci.yml").is_file()
    assert all(Path(p).is_absolute() for p in written)


def test_substitutes_service_name(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    pyproject = (tmp_path / "hello_users" / "pyproject.toml").read_text()
    assert 'name = "hello_users"' in pyproject
    assert "{{" not in pyproject and "{%" not in pyproject


def test_substitutes_model_snake(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    router = tmp_path / "hello_users" / "src" / "hello_users" / "api" / "routers" / "users.py"
    assert router.is_file()


def test_no_jinja_delimiters_in_output(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    for p in (tmp_path / "hello_users").rglob("*"):
        if p.is_file() and p.suffix in {".py", ".toml", ".yml", ".yaml", ".md"}:
            text = p.read_text(encoding="utf-8")
            assert "{{" not in text, f"jinja leak in {p}"
            assert "{%" not in text, f"jinja leak in {p}"


def test_idempotent(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    first = _sha_tree(tmp_path / "hello_users")
    render_service(schema, out_dir=tmp_path, force=True)
    second = _sha_tree(tmp_path / "hello_users")
    assert first == second


def test_refuses_overwrite_without_force(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    with pytest.raises(FileExistsError):
        render_service(schema, out_dir=tmp_path, force=False)


def test_force_overwrites_existing_dir(users_yaml_path: Path, tmp_path: Path) -> None:
    schema = load_schema(users_yaml_path)
    render_service(schema, out_dir=tmp_path)
    render_service(schema, out_dir=tmp_path, force=True)


def test_renderer_error_on_missing_template_dir(
    monkeypatch: pytest.MonkeyPatch,
    users_yaml_path: Path,
    tmp_path: Path,
) -> None:
    from feathers.generator import renderer

    monkeypatch.setattr(renderer, "TEMPLATE_ROOT", tmp_path / "does_not_exist")
    schema = load_schema(users_yaml_path)
    with pytest.raises(RendererError):
        render_service(schema, out_dir=tmp_path)


def test_renderer_error_on_bad_template_syntax(
    monkeypatch: pytest.MonkeyPatch,
    users_yaml_path: Path,
    tmp_path: Path,
) -> None:
    """Cover renderer.py:134-135,139-140 — bad template load/render."""
    import shutil

    from feathers.generator import renderer

    # Copy the real template tree
    custom_root = tmp_path / "templates"
    shutil.copytree(renderer.TEMPLATE_ROOT, custom_root)

    # Sabotage a template with broken Jinja
    broken = custom_root / "pyproject.toml.j2"
    broken.write_text("{% invalid block %}", encoding="utf-8")

    monkeypatch.setattr(renderer, "TEMPLATE_ROOT", custom_root)
    schema = load_schema(users_yaml_path)
    out = tmp_path / "out"
    with pytest.raises(RendererError):
        render_service(schema, out_dir=out)
