# Demo script

A 60-second walk-through. Copy-paste the blocks in order.

## 1. Install from PyPI

```bash
uv venv .demo --python 3.12
source .demo/Scripts/activate          # Windows
# source .demo/bin/activate            # Linux / macOS
uv pip install feathers-cli
feathers --help
```

## 2. Generate a service from the bundled demo schema

```bash
# The users.yaml demo ships inside the feathers-cli wheel. Grab a copy:
python -c "import feathers, shutil, pathlib; shutil.copy(pathlib.Path(feathers.__file__).parent / 'demos' / 'users.yaml', 'users.yaml')"

feathers lint users.yaml
feathers new --schema users.yaml --name hello_users --out .
```

You should see:

```
ok: generated hello_users in .
```

## 3. Boot the generated service

```bash
cd hello_users
uv sync
uv run uvicorn hello_users.main:app --port 8000
```

In another terminal:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"hello_users","version":"0.1.0","commit_sha":"unknown","db":"ok"}

curl http://localhost:8000/version
# {"service":"hello_users","version":"0.1.0","commit_sha":"unknown"}
```

`/health` and `/version` come for free via the platform middleware that every
generated service installs at boot. Request IDs are propagated as
`x-request-id` headers.

Two fields are worth reading closely:

- `db` is a live probe (`SELECT 1`), so it is only ever `"ok"` or `"down"` — never a
  placeholder. Above it is `"ok"` because no `DATABASE_URL` is set, so the service
  fell back to a local SQLite file and created the schema during startup. Point
  `DATABASE_URL` at Postgres and the same probe reports on that connection instead
  (there, the schema is owned by Alembic — run `uv run alembic upgrade head` first).
- `commit_sha` is read from `GIT_SHA`, falling back to `RENDER_GIT_COMMIT`; with
  neither set locally it reports `"unknown"`, while a Render deploy reports the real
  deployed SHA.

## 4. Add a new endpoint without rewriting your code

Edit `hello_users/src/hello_users/api/routers/users.py` and add a custom block:

```python
# feathers: begin hand-written
AUDIT_ENABLED = True
# feathers: end hand-written
```

Now extend `users.yaml` with a new endpoint, e.g.:

```yaml
  - { method: GET, path: "/users/{id}/audit", handler: users.audit, auth: admin }
```

Re-run from the parent directory:

```bash
feathers add endpoint --schema users.yaml --service hello_users
```

The new `users_audit` function is appended to the router. Your
`AUDIT_ENABLED` line is untouched. Running the same command a second time is
a no-op — the patcher is idempotent.
