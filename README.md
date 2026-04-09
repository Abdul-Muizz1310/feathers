# `feathers`

> Scaffold production FastAPI services from one YAML file — in under 10 seconds.

[PyPI](https://pypi.org/project/feathers-cli/) · [Why](WHY.md) · [Architecture](docs/ARCHITECTURE.md) · [Demo](docs/DEMO.md) · [Schema Example](demos/users.yaml)

![pypi](https://img.shields.io/pypi/v/feathers-cli?style=flat-square)
![python](https://img.shields.io/badge/python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)
![ci](https://img.shields.io/github/actions/workflow/status/Abdul-Muizz1310/feathers/ci.yml?style=flat-square)
![coverage](https://img.shields.io/badge/coverage-86%25-yellow?style=flat-square)
![mypy](https://img.shields.io/badge/mypy-strict-blue?style=flat-square)
![license](https://img.shields.io/github/license/Abdul-Muizz1310/feathers?style=flat-square)

---

## What it is

`feathers` is a CLI that reads a **single YAML schema** and emits a production-ready, MVC-structured **FastAPI service** — with tests, migrations, observability, CI, platform middleware, and Docker, all wired up and running.

Unlike a cookiecutter (which gives you a dead tree the moment you touch it), `feathers add` uses **libcst AST rewriting** to slot new code into existing services without clobbering a single line you wrote. Regeneration stays safe for the lifetime of the project.

---

## Why it's different

| Most scaffolders | `feathers` |
|---|---|
| Cookiecutter templates — stale after first edit | **Incremental AST codegen** — regeneration stays safe forever |
| String templating | **Pydantic v2 schema** validated before any file is written |
| Hand-wired middleware per service | **Platform middleware** shipped with every generated service |
| You protect your edits with prayer | **Fence markers** (`# feathers: begin hand-written`) — regen never touches protected regions |
| Pick your own stack | **Opinionated & consistent** — FastAPI + uv + Alembic + structlog + Prometheus + OpenTelemetry |

---

## Quick start

```bash
pip install feathers-cli

feathers new --schema demos/users.yaml --name hello-users --out .
cd hello-users && make run
# → http://localhost:8000/docs
```

Add an endpoint later without regenerating the whole service:

```bash
# edit demos/users.yaml → append a new endpoint
feathers add endpoint --schema demos/users.yaml --service ./hello-users
```

Your hand-written code between `# feathers: begin hand-written` fences stays untouched.

---

## CLI reference

| Command | Purpose |
|---|---|
| `feathers new --schema FILE --name NAME --out DIR` | Generate a new service from a schema |
| `feathers add endpoint --schema FILE --service DIR` | Slot a new endpoint into an existing service |
| `feathers add model --schema FILE --service DIR` | Add a new model stub |
| `feathers lint SCHEMA` | Validate a YAML schema without generating |
| `feathers doctor` | Environment health check (Python, uv) |
| `feathers bench` *(v0.2)* | Run Locust benchmarks against a generated service |

---

## How it works

```mermaid
flowchart TD
    YAML[schema.yaml] --> Loader[loader<br/>YAML → dict]
    Loader --> Schema[schema<br/>Pydantic v2 frozen validation]
    Schema --> Context[context<br/>type mapping · snake/pascal · plural]
    Context --> Renderer[renderer<br/>Jinja2 · 21 templates]
    Context --> Patcher[ast_patcher<br/>libcst · for feathers add]
    Renderer --> Service[Generated FastAPI service]
    Patcher --> Service
```

### `new` vs `add`

```mermaid
sequenceDiagram
    participant User
    participant CLI as feathers CLI
    participant Val as Pydantic validator
    participant Gen as Jinja renderer
    participant AST as libcst patcher
    participant FS as File system

    User->>CLI: feathers new
    CLI->>Val: validate schema
    Val-->>CLI: ok
    CLI->>Gen: render 21 templates
    Gen->>FS: write full service tree

    User->>CLI: feathers add endpoint
    CLI->>Val: validate schema
    Val-->>CLI: ok
    CLI->>AST: patch routers/*.py
    AST->>FS: read existing file
    AST->>AST: find marker fences
    AST->>AST: insert between markers
    AST->>FS: write file (hand-written code untouched)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the deep dive.

---

## Schema anatomy

```yaml
service:
  name: hello_users
  description: A minimal users service
  python: "3.12"

models:
  - name: User
    fields:
      - { name: id,       type: uuid,     primary: true }
      - { name: email,    type: str,      unique: true, indexed: true }
      - { name: name,     type: str }
      - { name: created,  type: datetime }
    soft_delete: true
    audit: true

endpoints:
  - { method: GET,  path: /users/{id}, handler: user.get,    auth: any }
  - { method: POST, path: /users,      handler: user.create, auth: admin }
  - { method: GET,  path: /users,      handler: user.list,   auth: any, paginate: cursor }

observability:
  metrics: prometheus
  tracing: otel
  logging: structlog

deploy:
  target: render
  min_instances: 1
  health: /health
```

Every field is validated by **frozen Pydantic v2 models** — if the schema is wrong, `feathers` refuses to write a single file.

---

## Generated service layout

```
hello-users/
├── src/hello_users/
│   ├── main.py                  # FastAPI app + middleware
│   ├── api/routers/             # One router per model
│   ├── services/                # Business logic layer
│   ├── repositories/            # Data access layer
│   ├── models/                  # Dataclass stubs (SQLAlchemy wiring in v0.2)
│   ├── schemas/                 # Pydantic DTOs
│   └── core/
│       └── platform.py          # /health, /version, X-Request-ID, X-Platform-Token
├── tests/
│   └── test_health.py
├── .github/workflows/ci.yml     # lint → test → build
├── Dockerfile
├── Makefile                     # make run | test | lint | format | typecheck
├── render.yaml                  # one-click Render deploy
└── pyproject.toml               # uv-managed
```

---

## Tech stack

| Concern | Choice |
|---|---|
| CLI framework | **Typer** |
| YAML validation | **Pydantic v2** (frozen models) |
| Template engine | **Jinja2** (21 templates per service) |
| AST rewriting | **libcst** |
| Package manager | **uv** |
| Lint / Types | **ruff** + **mypy strict** |
| Tests | **pytest** + coverage |

---

## Engineering philosophy

| Principle | How it shows up |
|---|---|
| **Spec-TDD** | 45 tests across loader, schema, renderer, AST patcher, CLI. Red-first. |
| **Negative-space programming** | `Literal` types for field types, HTTP methods, auth roles. Frozen Pydantic models. Schema validation rejects invalid input before any file is written. |
| **MVC-style layering** *(adapted for CLI)* | `cli → generator → schema`. Each layer has one responsibility and never reaches across. |
| **Typed everything** | `mypy --strict` passes. No `any` in source. Public APIs fully type-hinted. |
| **Pure core, imperative shell** | Schema validation, context building, and rendering are pure. File I/O lives only in the CLI entry points. |
| **One responsibility per module** | `loader` (I/O), `service` (schema defs), `context` (view transforms), `renderer` (Jinja), `ast_patcher` (AST). |

---

## Testing

```bash
make test                                  # full suite
uv run pytest --cov=src/feathers --cov-report=term-missing
uv run pytest -m "not slow"                # skip e2e generation + boot
```

| Metric | Value |
|---|---|
| **Test count** | 45 tests |
| **Coverage** | **86%** (target: 100%) |
| **E2E** | `@pytest.mark.slow` — generates the users service, `uv sync`, boots uvicorn, hits `/health` |
| **CI** | GitHub Actions: ruff → mypy → pytest → `uv build` |

### Roadmap to 100% coverage

| Module | Current | Gap |
|---|---|---|
| `cli.py` | 73% | `add_endpoint` / `add_model` error paths, name-mismatch warning |
| `generator/context.py` | 88% | `plural()` edge cases (`"entry" → "entries"`, `"status" → "status"`) |
| `generator/renderer.py` | 92% | Template load / render error paths |
| `schema/loader.py` | 94% | `OSError` on file read, YAML non-dict root |
| `generator/ast_patcher.py` | 96% | Missing `routers_dir` / `models_dir` error branches |

---

## Benchmarks *(v0.2 target)*

| Metric | Target |
|---|---|
| Generated `GET /users/{id}` throughput | ≥ 10,000 req/s |
| Generated `GET /users/{id}` p99 latency | < 30 ms |

Run via `feathers bench` (Locust) against local Postgres.

---

## Deployment

- **`feathers-cli` itself** → published to PyPI on `v*` tag push via GitHub Actions
- **Generated services** → deploy to **Render**, **Fly.io**, or **Docker** (target chosen in schema)

---

## Contributing

```bash
git clone https://github.com/Abdul-Muizz1310/feathers.git
cd feathers
uv sync --all-extras
make test
make lint
```

Guidelines:

1. Open an issue before non-trivial PRs
2. Red-first TDD — failing test in the commit before the fix
3. `make lint typecheck test` must pass

---

## License

MIT — see [LICENSE](LICENSE).

---

> *Built to make regenerating FastAPI services boring.*
