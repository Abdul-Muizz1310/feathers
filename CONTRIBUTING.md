# Contributing to feathers

Welcome! Thanks for your interest in contributing to `feathers`. Whether you're fixing a bug, adding a template, or improving docs, this guide will help you get started quickly.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| **Python** | 3.12+ | [python.org](https://www.python.org/downloads/) |
| **uv** | latest | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| **git** | any recent | [git-scm.com](https://git-scm.com/) |

---

## Development setup

```bash
# 1. Clone the repo
git clone https://github.com/Abdul-Muizz1310/feathers.git
cd feathers

# 2. Install all dependencies (including dev extras)
uv sync --all-extras

# 3. Run the test suite
make test

# 4. Run linters + type checker
make lint
```

If everything passes, you're ready to contribute.

### Useful Makefile targets

| Target | What it does |
|---|---|
| `make test` | Run full pytest suite |
| `make lint` | ruff check + ruff format --check + mypy |
| `make format` | Auto-format with ruff |
| `make typecheck` | mypy strict only |
| `make build` | Build distribution with uv |
| `make clean` | Remove build artifacts, caches |

---

## Project structure

```
feathers/
├── src/feathers/
│   ├── cli.py                       # Typer CLI — entry point for all commands
│   ├── generator/
│   │   ├── ast_patcher.py           # libcst AST rewriting (feathers add)
│   │   ├── context.py               # Schema → template context transforms
│   │   └── renderer.py              # Jinja2 template rendering engine
│   ├── schema/
│   │   ├── loader.py                # YAML file → dict I/O
│   │   ├── service.py               # Pydantic v2 frozen schema models
│   │   └── errors.py                # Schema validation error types
│   ├── templates/service/           # 21 Jinja2 templates for generated services
│   └── demos/                       # Example YAML schemas
├── tests/
│   ├── unit/                        # Per-module unit tests
│   │   ├── test_ast_patcher.py
│   │   ├── test_cli.py
│   │   ├── test_context.py
│   │   ├── test_renderer.py
│   │   └── test_schema.py
│   └── e2e/                         # End-to-end: generate → boot → hit /health
│       └── test_generate_and_run.py
├── Makefile
├── pyproject.toml
└── WHY.md
```

---

## How to add a new template

Templates live in `src/feathers/templates/service/`. Each `.j2` file is rendered by `generator/renderer.py` using context built by `generator/context.py`.

### Steps

1. **Create the template file** in the appropriate subdirectory under `templates/service/`. Use Jinja2 syntax with the context variables defined in `context.py`.

2. **Register the template** in `generator/renderer.py` — add it to the list of templates that get rendered during `feathers new`.

3. **Add context variables** if needed — extend the context dataclass in `generator/context.py` with any new fields your template requires.

4. **Write tests** — add a test in `tests/unit/test_renderer.py` that verifies the template renders correctly with sample input. Check both valid output and edge cases.

5. **Update the template count** in docs if the total changes (currently 21).

### Conventions

- Template filenames end in `.j2`
- Output paths mirror the generated service's directory structure
- Use `{{ variable }}` for simple substitution, `{% for %}` for iteration
- Include comments in templates explaining non-obvious logic

---

## How to add a new schema field type

Field types are defined as `Literal` values in the Pydantic models in `src/feathers/schema/service.py`. The type-mapping logic lives in `src/feathers/generator/context.py`.

### Steps

1. **Add the type to the `Literal`** union in `schema/service.py` (e.g., add `"jsonb"` to the field type literal).

2. **Add the Python type mapping** in `context.py` — map the new YAML type to its Python equivalent (e.g., `"jsonb" → "dict[str, Any]"`).

3. **Update any templates** that reference field types if the new type needs special handling (imports, validation, etc.).

4. **Write tests**:
   - Schema test: verify the new type is accepted in valid schemas and rejected when misspelled
   - Context test: verify the type mapping produces the correct Python type
   - Renderer test: verify templates render correctly with the new type

5. **Add an example** to a demo YAML schema showing the new type in use.

---

## How to add a new CLI command

CLI commands are defined in `src/feathers/cli.py` using Typer.

### Steps

1. **Define the command** in `cli.py` using `@app.command()` or as a subcommand on an existing group.

2. **Keep the command thin** — it should parse arguments, call into `generator/` or `schema/`, and handle I/O. Business logic belongs in the generator or schema layer, not in the CLI.

3. **Add Typer type hints** for all parameters — use `typer.Option()` and `typer.Argument()` with help text.

4. **Write tests** in `tests/unit/test_cli.py`:
   - Happy path: command succeeds with valid input
   - Error paths: missing arguments, invalid schema, file not found
   - Use `typer.testing.CliRunner` for invocation

5. **Update the CLI reference table** in `README.md`.

---

## Testing guidelines

This project follows **Spec-Based Test-Driven Development (Spec-TDD)**. Every change must be test-driven.

### The process

1. **Write the spec** — describe the behavior, inputs, outputs, and invariants of the feature or fix.

2. **Enumerate test cases** — list explicit pass conditions AND failure conditions before writing any code:
   - Happy paths (valid input, expected output)
   - Edge cases (empty input, boundary values, unicode)
   - Error conditions (invalid schema, missing files, malformed YAML)
   - Invariants (fence markers preserved, existing code untouched)

3. **Write failing tests** that encode those conditions.

4. **Implement** the feature until all tests pass.

5. **Never mark done** until every enumerated failure case is covered.

### Running tests

```bash
# Full suite
make test

# With coverage
uv run pytest --cov=src/feathers --cov-report=term-missing

# Skip slow E2E tests
uv run pytest -m "not slow"

# Run a single test file
uv run pytest tests/unit/test_schema.py -v

# Run a single test
uv run pytest tests/unit/test_schema.py::test_name -v
```

### Test organization

- **Unit tests** go in `tests/unit/` — one test file per source module
- **E2E tests** go in `tests/e2e/` — mark with `@pytest.mark.slow`
- Test files mirror source structure: `schema/service.py` → `unit/test_schema.py`

---

## Code style

### Formatting & linting

- **ruff** handles both formatting and linting
- **mypy strict** is enforced — no `Any`, no untyped defs, no implicit optionals
- Run `make format` to auto-fix formatting before committing
- Run `make lint` to check everything

### Principles

- **No `Any`** — every public function is fully type-hinted
- **Frozen Pydantic models** — schema types are immutable by design
- **`Literal` types over strings** — field types, HTTP methods, and auth roles use `Literal` unions
- **One responsibility per module** — if a module name needs "and" to describe it, split it
- **Pure core, imperative shell** — schema validation, context building, and rendering are pure functions. File I/O and side effects live at the CLI boundary.

---

## PR process

### Before opening a PR

1. **Open an issue first** for non-trivial changes — discuss the approach before writing code
2. **Follow Spec-TDD** — your PR should include both tests and implementation
3. **Run the full CI gate locally**:

```bash
make lint       # ruff check + format check + mypy strict
make test       # full pytest suite including E2E
make build      # verify the package builds
```

All three must pass before opening a PR.

### PR checklist

- [ ] Spec written (behavior, inputs, outputs, invariants)
- [ ] Test cases enumerated (pass + failure conditions)
- [ ] Failing tests written and committed
- [ ] Implementation makes all tests pass
- [ ] `make lint` passes (ruff + mypy strict)
- [ ] `make test` passes (all tests including E2E)
- [ ] `make build` succeeds
- [ ] README updated if CLI commands or template count changed
- [ ] No `Any` types introduced

### Review

- PRs are reviewed for correctness, test coverage, type safety, and adherence to project architecture
- Small, focused PRs are preferred over large changes
- Each PR should address a single concern

---

## Commit conventions

- Use **imperative mood** in commit messages: "Add cursor pagination field type", not "Added" or "Adds"
- Keep the subject line under 72 characters
- Reference related issues: `Fix #42 — handle empty YAML files`
- Separate subject from body with a blank line if more detail is needed
- **Red-first commits**: when practical, commit the failing test before the implementation so the history shows the TDD flow

---

## Running the full CI gate locally

The GitHub Actions CI runs these steps in order. Reproduce them locally before pushing:

```bash
# 1. Lint and format check
uv run ruff check .
uv run ruff format --check .

# 2. Type check
uv run mypy src/

# 3. Test suite with coverage
uv run pytest --cov=src/feathers --cov-report=term-missing

# 4. Build
uv build
```

Or use the Makefile shortcuts:

```bash
make lint && make test && make build
```

---

## Where to ask questions

- **GitHub Issues** — [Abdul-Muizz1310/feathers/issues](https://github.com/Abdul-Muizz1310/feathers/issues)
- Open an issue for bugs, feature requests, or questions about the codebase
- Tag your issue with the appropriate label (`bug`, `enhancement`, `question`)

---

Thanks for contributing! Every test, template, and type annotation makes `feathers` better for everyone.
