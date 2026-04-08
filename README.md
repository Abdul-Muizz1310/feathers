<p align="center">
  <img src="assets/demo.gif" alt="demo" width="720"/>
</p>

<h1 align="center">feathers</h1>
<p align="center">
  <em>Scaffold production FastAPI services from one YAML file, in under 10 seconds.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/feathers-cli/">PyPI</a> •
  <a href="WHY.md">Why</a> •
  <a href="docs/ARCHITECTURE.md">Architecture</a> •
  <a href="docs/DEMO.md">Demo Script</a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/Abdul-Muizz1310/feathers/ci.yml" alt="ci"/>
  <img src="https://img.shields.io/github/license/Abdul-Muizz1310/feathers" alt="license"/>
</p>

---

## What it does

`feathers` is a CLI that takes a YAML schema and emits an opinionated, MVC-structured
FastAPI service with tests, migrations, observability, CI, and Docker — all wired up.
Unlike a cookiecutter, `feathers add` rewrites the AST of an existing service so you
can keep regenerating without clobbering hand-written code.

## The unique angle

- **AST-aware incremental mode** (libcst) — `feathers add endpoint` slots new code into
  existing files without touching a line you wrote
- **Hand-written fence markers** — anything between `# feathers: begin hand-written`
  and `# feathers: end hand-written` is never rewritten
- **One-file schema** — YAML defines models, endpoints, observability, and deploy target
- **Typed everything** — Pydantic v2 validates the schema before a single file is written
- **Ships the platform middleware** — every generated service gets `/health`, `/version`,
  `/metrics`, request ID propagation, and JWT validation out of the box

## Quick start

```bash
pip install feathers-cli
feathers new --schema demos/users.yaml --name hello-users --out .
cd hello-users && make run
# → http://localhost:8000/docs
```

## Benchmarks

| Metric | Target |
|---|---|
| Generated `GET /users/{id}` sustained throughput | ≥10,000 req/s |
| Generated `GET /users/{id}` p99 latency | <30 ms |

Benchmarks run via `feathers bench` (Locust) against a local Postgres.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

| Concern | Choice |
|---|---|
| CLI framework | Typer |
| Template engine | Jinja2 |
| YAML validation | Pydantic v2 |
| AST rewriting | libcst |
| Package manager | uv |

## Deployment

- **PyPI**: published on `v*` tag push via GitHub Actions
- **Generated services**: deploy to Render, Fly.io, or Docker (target chosen in schema)

## License

MIT — see [LICENSE](LICENSE).
