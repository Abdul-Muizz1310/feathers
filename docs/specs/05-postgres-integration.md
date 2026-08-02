# 05 — Postgres integration tier (Testcontainers)

## Goal

`feathers` is a code **generator**. Everything in `tests/unit/` and `tests/e2e/` proves the
*generator* behaves — the e2e tier even boots the generated service, but with no
`DATABASE_URL`, so it only ever exercises the `sqlite+aiosqlite` fallback in
`core/db.py`.

This tier proves the *generated service* works against the database it is actually
deployed on: real Postgres, reached over TCP, with the schema created by the generated
Alembic migration rather than by the SQLite-only `init_models()` startup path.

That split matters because three generated code paths are **unreachable** under SQLite
and therefore untested by every other tier:

1. `main.py` `lifespan` skips `init_models()` for non-SQLite dialects, so the schema
   must come from `alembic upgrade head` — the same command `render.yaml` runs as
   Render's `preDeployCommand`. If that migration is broken, only Postgres shows it.
2. `get_engine()` only passes `pool_pre_ping` / `pool_recycle` on non-SQLite URLs.
3. Column types resolve differently: `Uuid()` becomes a native Postgres `uuid`
   (SQLite stores `CHAR(32)`), and `DateTime(timezone=True)` becomes
   `timestamptz` (SQLite ignores the timezone flag). Keyset pagination compares the
   UUID primary key with `>`, which is a genuinely different operator on each.

## Inputs / Outputs

- **Input**: the bundled `demos/users.yaml` and a throwaway Postgres container.
- **Pipeline**: YAML → `render_service` → `uv sync` →
  `uv run alembic upgrade head` (with `DATABASE_URL` set to the container) →
  `uv run uvicorn` → HTTP.
- **Marker**: `@pytest.mark.integration`, registered in `pyproject.toml`. The fast tier is
  `pytest -m "not slow and not integration"`.
- **Skip contract**: the tier **skips** — never fails — when the Docker daemon is
  unreachable (`docker info` non-zero / `docker` absent). Any other failure, including a
  container that starts but never becomes ready, is a real failure and must surface.

## Invariants

- `DATABASE_URL` is passed to the generated service as a `postgresql+asyncpg://` DSN;
  the service must not silently fall back to SQLite. Enforced negatively: after the run,
  no `*.db` SQLite file may exist anywhere in the generated project.
- Rows written over HTTP are visible to a **separate** Postgres client (`psql` inside the
  container). This is what makes the tier meaningful rather than self-confirming.
- The container is per-module and torn down by the fixture, including on failure.

## Test cases

- `test_health_reports_postgres_ok` — `GET /health` returns 200 with `db == "ok"` and
  `service == "hello_users"`, proving the live `SELECT 1` probe ran against Postgres.
- `test_alembic_created_the_model_table` — `alembic upgrade head` (already run by the
  fixture, since booting depends on it) left a `users` table plus the
  `alembic_version` bookkeeping table in the container's `public` schema.
- `test_uuid_primary_key_is_native_postgres_uuid` — `users.id` has
  `data_type = 'uuid'` and `created_at` / `updated_at` are `timestamp with time zone`,
  i.e. the generated column types survive the SQLAlchemy → Postgres mapping.
- `test_created_row_is_visible_to_a_separate_postgres_client` — `POST /users` returns
  201, and a `psql` query run inside the container finds exactly that row by `id`. The
  `created_at`/`updated_at` server defaults are non-null.
- `test_crud_roundtrip_against_postgres` — create → get (200) → list (contains the row)
  → patch (200, field changed) → get unknown UUID (404).
- `test_soft_delete_hides_row_everywhere_but_keeps_it_in_postgres` — `DELETE /users/{id}`
  returns 204; the row then disappears from `GET /users`, `GET /users/{id}` returns 404,
  a second `DELETE` returns 404, and `psql` still finds the row with a non-null
  `deleted_at`. Soft delete must be indistinguishable from absence to every reader and
  writer, yet must not become a hard delete on Postgres. (This case is what caught the
  generated repository bug where only `list` filtered `deleted_at`, so a client that had
  just received 204 could still `GET` and re-`DELETE` the row forever.)
- `test_cursor_pagination_pages_forward_without_repeats` — with three rows, `?limit=1`
  followed by `?cursor=<last id>` walks the keyset in ascending `id` order and never
  repeats a row (Postgres `uuid` `>` comparison, not SQLite's string comparison).
- `test_no_sqlite_file_was_created` — the negative-space guard for the invariant above.

## Acceptance

- Every case above passes against `postgres:17-alpine`.
- CI runs the tier in a dedicated `integration` job (ubuntu-latest ships a Docker
  daemon); the main `test` job stays on `-m "not integration"` so coverage timing is
  unaffected.
- Dependencies: `testcontainers[postgres]` in the `dev` extra only — it never becomes a
  runtime dependency of `feathers-cli`, and the *generated* project's dependency list is
  unchanged.
