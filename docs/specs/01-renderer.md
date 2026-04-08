# 01 — Jinja2 template renderer

## Goal

Given a validated `ServiceSchema` and an output directory, render every file in the
service template tree with Jinja2 substitutions resolved, writing the result to disk.

## Inputs / Outputs

- **Input**: `ServiceSchema`, `out_dir: Path`, `force: bool`.
- **Output**: list of written file paths (absolute).
- **Side effect**: files created on disk under `out_dir / service.name`.

## Invariants

- Rendering is **idempotent** — re-running with the same inputs writes byte-identical
  output (except file mtimes).
- No Jinja delimiters (`{{ }}`, `{% %}`) appear in any output file.
- All generated paths use forward slashes when stored in `pyproject.toml` etc., and
  the physical write uses `pathlib.Path` (handles Windows).
- If `out_dir / service.name` already exists and `force=False`, raise `FileExistsError`
  before writing anything.

## Test cases

### Success

- `test_renders_users_demo` — given `demos/users.yaml`, produces the expected file list
  (snapshot test against a committed list in `tests/fixtures/users_demo_files.txt`).
- `test_substitutes_service_name` — the generated `pyproject.toml` contains
  `name = "hello_users"` not `{{ service_name }}`.
- `test_substitutes_model_snake` — router file is named `users.py` (from `User` model).
- `test_idempotent` — call `render()` twice, assert all output files have identical SHA-256.
- `test_force_overwrites_existing_dir` — pre-create the target dir, call with `force=True`, succeeds.
- `test_refuses_overwrite_without_force` — pre-create the target dir, call with
  `force=False`, raises `FileExistsError`.

### Failure

- `test_missing_template_file_raises` — if `templates/` is somehow empty, raises
  `RendererError` naming the template package.
- `test_jinja_syntax_error_in_template` — simulated by patching, raises
  `RendererError` with template filename.

## Acceptance

- Renders `demos/users.yaml` in <2 seconds.
- Every template file lives under `src/feathers/templates/service/`.
- No line of output contains `{{` or `{%`.
