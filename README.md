<p align="center">
  <img src="assets/demo.gif" alt="feathers demo" width="720" onerror="this.style.display='none'"/>
</p>

<h1 align="center"><code>feathers</code></h1>

<p align="center">
  <em>Scaffold production FastAPI services from one YAML file — in under 10 seconds.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/feathers-cli/">PyPI</a> •
  <a href="WHY.md">Why</a> •
  <a href="docs/ARCHITECTURE.md">Architecture</a> •
  <a href="docs/DEMO.md">Demo</a> •
  <a href="demos/users.yaml">Schema Example</a>
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/v/feathers-cli?style=flat-square" alt="pypi"/>
  <img src="https://img.shields.io/badge/python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white" alt="python"/>
  <img src="https://img.shields.io/github/actions/workflow/status/Abdul-Muizz1310/feathers/ci.yml?style=flat-square" alt="ci"/>
  <img src="https://img.shields.io/badge/coverage-86%25-yellow?style=flat-square" alt="coverage"/>
  <img src="https://img.shields.io/badge/mypy-strict-blue?style=flat-square" alt="mypy"/>
  <img src="https://img.shields.io/github/license/Abdul-Muizz1310/feathers?style=flat-square" alt="license"/>
</p>

---

## What it is

`feathers` is a CLI that reads a **single YAML schema** and emits a production-ready, MVC-structured **FastAPI service** — with tests, migrations, observability, CI, platform middleware, and Docker, all wired up and running.

Unlike a cookiecutter (which gives you a dead tree the moment you touch it), `feathers add` uses **libcst AST rewriting** to slot new code into existing services without clobbering a single line you wrote. Regeneration stays safe for the lifetime of the project.

## Why it's different

| Most scaffolders | `feathers` |
|---|---|
| Cookiecutter templates — stale after first edit | **Incremental AST codegen** — regeneration stays safe forever |
| String templating | **Pydantic v2 schema** validated before any file is written |
| Hand-wired middleware per service | **Platform middleware** shipped with every generated service |
| You protect your edits with prayer | **Fence markers** (`# feathers: begin hand-written`) — regen never touches protected regions |
| Pick your own stack | **Opinionated & consistent** — FastAPI + uv + Alembic + structlog + Prometheus + OpenTelemetry |

## Quick start

```bash
pip install feathers-cli

feathers new --schema demos/users.yaml --name hello-users --out .
cd hello-users && make run
# → http://localhost:8000/docs
```

Then, to add an endpoint later without regenerating the whole service:

```bash
# edit demos/users.yaml → append a new endpoint
feathers add endpoint --schema demos/users.yaml --service ./hello-users
```

Your hand-written code between `# feathers: begin hand-written` fences stays untouched.

## CLI reference

| Command | Purpose |
|---|---|
| `feathers new --schema FILE --name NAME --out DIR` | Generate a new service from a schema |
| `feathers add endpoint --schema FILE --service DIR` | Slot a new endpoint into an existing service |
| `feathers add model --schema FILE --service DIR` | Add a new model stub |
| `feathers lint SCHEMA` | Validate a YAML schema without generating |
| `feathers doctor` | Environment health check (Python, uv) |
| `feathers bench` _(v0.2)_ | Run Locust benchmarks against a generated service |

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
  - { method: GET,    path: /users/{id}, handler: user.get,    auth: any    }
  - { method: POST,   path: /users,      handler: user.create, auth: admin  }
  - { method: GET,    path: /users,      handler: user.list,   auth: any, paginate: cursor }

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

## What a generated service looks like

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

## Architecture

```
            ┌──────────────┐
            │  schema.yaml │
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │   loader     │  ← YAML → dict
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │   schema     │  ← Pydantic v2 validation (frozen models)
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │   context    │  ← type mapping, snake/pascal case, pluralization
            └──────┬───────┘
                   ▼
       ┌───────────┴────────────┐
       ▼                        ▼
┌──────────────┐         ┌──────────────┐
│   renderer   │         │ ast_patcher  │  ← libcst (for `feathers add`)
│   (Jinja2)   │         │              │
└──────┬───────┘         └──────┬───────┘
       └───────────┬────────────┘
                   ▼
            ┌──────────────┐
            │  FastAPI     │
            │  service     │
            └──────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the deep dive.

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

## Engineering philosophy

| Principle | How it shows up |
|---|---|
| **Spec-TDD** | 45 tests across loader, schema, renderer, AST patcher, CLI. Red-first. |
| **Negative-space programming** | `Literal` types for field types, HTTP methods, auth roles. Frozen Pydantic models. Schema validation rejects invalid input before any file is written. |
| **MVC-style layering** _(adapted for CLI)_ | `cli → generator → schema`. Each layer has one responsibility and never reaches across. |
| **Typed everything** | `mypy --strict` passes. No `any` in source. Public APIs fully type-hinted. |
| **Pure core, imperative shell** | Schema validation, context building, and rendering are pure. File I/O lives only in the CLI entry points. |
| **One responsibility per module** | `loader` (I/O), `service` (schema defs), `context` (view transforms), `renderer` (Jinja), `ast_patcher` (AST). |

## Testing

```bash
make test                                  # full suite
uv run pytest --cov=src/feathers --cov-report=term-missing
uv run pytest -m "not slow"                # skip e2e generation + boot
```

<table>
<tr><td><strong>Test count</strong></td><td>45 tests</td></tr>
<tr><td><strong>Coverage</strong></td><td><strong>86%</strong> (target: 100%)</td></tr>
<tr><td><strong>E2E</strong></td><td><code>@pytest.mark.slow</code> — generates the users service, <code>uv sync</code>, boots uvicorn, hits <code>/health</code></td></tr>
<tr><td><strong>CI</strong></td><td>GitHub Actions: ruff → mypy → pytest → <code>uv build</code></td></tr>
</table>

### Roadmap to 100% coverage

| Module | Current | Gap |
|---|---|---|
| `cli.py` | 73% | `add_endpoint` / `add_model` error paths, name-mismatch warning |
| `generator/context.py` | 88% | `plural()` edge cases ("entry" → "entries", "status" → "status") |
| `generator/renderer.py` | 92% | Template load / render error paths |
| `schema/loader.py` | 94% | `OSError` on file read, YAML non-dict root |
| `generator/ast_patcher.py` | 96% | Missing `routers_dir` / `models_dir` error branches |

## Benchmarks _(v0.2 target)_

| Metric | Target |
|---|---|
| Generated `GET /users/{id}` throughput | ≥ 10,000 req/s |
| Generated `GET /users/{id}` p99 latency | < 30 ms |

Run via `feathers bench` (Locust) against local Postgres.

## Deployment

- **`feathers-cli` itself** → published to PyPI on `v*` tag push via GitHub Actions
- **Generated services** → deploy to **Render**, **Fly.io**, or **Docker** (target chosen in schema)

## Contributing

```bash
git clone https://github.com/Abdul-Muizz1310/feathers.git
cd feathers
uv sync --all-extras
make test
make lint
```

Please:
1. Open an issue before non-trivial PRs
2. Red-first TDD — failing test in the commit before the fix
3. `make lint typecheck test` must pass

## License

MIT — see [LICENSE](LICENSE).

<p align="center"><sub><em>Built to make regenerating FastAPI services boring.</em></sub></p>
