# Changelog

All notable changes to `feathers-cli`. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) (pre-1.0: a minor bump may break).

## [0.2.0] — 2026-10-20

The first release since 0.1.1 (2026-04-10). It ships everything below, including the
June–August generator work that was on `main` but never published.

### What a generated service is now

- **Real persistence.** Each model emits a SQLAlchemy 2 ORM table, Pydantic
  Create/Update/Response DTOs, an async repository, a service layer and CRUD routes on an
  async session; SQLite by default, Postgres via `DATABASE_URL`, schema from a generated
  Alembic `0001` migration. Postgres engines use `pool_pre_ping` and a short `pool_recycle`.
- **Platform token contract v2** (`core/platform_token.py`). Every route except
  `/health`, `/version`, `/metrics`, the docs and endpoints declared `auth: none` needs an
  EdDSA JWT signed by bastion (`X-Platform-Token`, else `Authorization: Bearer`) with
  `iss == "bastion"` and `aud` equal to the service id, a constant derived from the schema
  name (`feathers_demo` → `feathers-demo`). Claims are parsed strictly (a list `aud`, a
  float `exp`, an unknown `role` are rejected); `exp`/`iat` have 10 s of leeway and
  `exp - iat` must be at most 300 s. A present-but-invalid token is 401
  `invalid_platform_token`, a missing one 401 `missing_platform_token`; with no key
  configured protected routes answer 503 `platform_auth_unconfigured`. The key comes from
  `BASTION_SIGNING_KEY_PUBLIC` (base64 SPKI DER) or `BASTION_PUBLIC_KEY_URL` (cached an hour).
- **Roles.** `require_role` enforces each endpoint's `auth:` (`viewer < editor < admin`;
  `frontend` ranks as `viewer`; `any` = any valid token) with 403 `insufficient_role`.
- **Rate limiting** (`core/rate_limit.py`): a per-process fixed window,
  `RATE_LIMIT_PER_MINUTE` (default 120), keyed `iss:sub` for an authenticated caller and the
  leftmost `X-Forwarded-For` address otherwise; 429 `rate_limited`.
- **CORS** allows exactly `authorization`, `content-type`, `x-platform-token` and
  `x-request-id`, without credentials, as the outermost middleware.
- **Pagination.** `paginate: cursor` emits keyset pagination on the primary key; `offset`
  (or `none`) offset pagination; both cap `limit` at 100. The repository and service emit
  only the list function an endpoint uses — no dead offset or keyset code.
- **Soft delete everywhere.** A soft-deleted row answers 404 to `GET`, `PATCH`/`PUT` and
  `DELETE` and is not listed, while staying in the database.
- **Project hygiene.** A `LICENSE` (MIT; copyright line from the schema's new
  `service.copyright`, default `2026 Abdul-Muizz Anwar`); ruff (`E F I B UP N SIM RUF`,
  line length 100) and strict mypy configuration in `pyproject.toml`, with `ruff`, `mypy`,
  `pytest` and `httpx2` in the `dev` extra; a CI `lint` job that runs `ruff check`,
  `ruff format --check` and `mypy`. The output passes all of them as generated.
- **Generated tests** prove it: the contract-v2 conformance cases that apply to a
  bastion-only service, role ranks, the limiter, CORS, and per-model CRUD, soft delete ⇒
  404 and declared roles ⇒ 403 — signed with a per-session test key, with no test-mode
  bypass. `tests/conftest.py` isolates the database per session and resets platform
  settings per test, so the suite is re-runnable; `.gitignore` ignores `*.db`.
- **Deploy.** `/metrics` (Prometheus) and `commit_sha` in `/health` and `/version`;
  the Dockerfile copies `README.md` and `LICENSE` before `pip install .`, runs as a
  non-root user and starts uvicorn with `--proxy-headers --forwarded-allow-ips *`;
  `render.yaml` asks for `BASTION_SIGNING_KEY_PUBLIC`.

### CLI and generator

- `feathers bench` measures generation throughput.
- `feathers add endpoint` keeps an added endpoint's declared role guard and leaves the
  router ruff-clean; it refuses (instead of emitting a `NameError`) when the router does
  not import `require_role`.
- Rendering is deterministic, and a golden manifest (`tests/fixtures/users_demo.sha256`)
  makes every change to the generated demo tree a deliberate diff.
- `__version__` is read from the installed package metadata.

### Breaking

- Generated services **fail closed**: `DEMO_MODE` now defaults to `false` and only
  tolerates a *missing* token; with no bastion key every protected route answers 503
  (0.1 failed open). Tokens must carry `aud` = the service id, `iss = "bastion"`, `sub`,
  `role`, `iat` and `exp`. Error bodies are `{"detail": "<code>"}`.
- `auth: none` endpoints are public (no token at all); previously the middleware still
  demanded a token once a key was configured.
- Schema: `service.name` must be an identifier (`[A-Za-z][A-Za-z0-9_]*`), endpoint path
  segments must be plain (`A-Z a-z 0-9 . _ ~ -`) or `{param}`, and the inert
  `observability.tracing` and `deploy.target` keys are rejected.

## [0.1.1] — 2026-04-10

- Lint fixes, coverage raised to 99%.

## [0.1.0] — 2026-04-09

- First release: `feathers new`, `add endpoint`, `add model`, `lint`, `doctor`; Jinja2
  templates for a FastAPI service with platform middleware.
