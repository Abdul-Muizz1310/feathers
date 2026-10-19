# 07 — Generated project hygiene (0.2.0)

## Goal

Close the generator-level gaps that `feathers_demo` exposed (`docs/REMAINING-WORK.md` in
the meta-repo): a generated project ships a licence, carries its own lint and type
configuration and passes it, contains no dead code, honours soft delete on every
primary-key path, and has a test suite that is isolated and re-runnable. Every fix lives
in `src/feathers/templates/`, so `feathers_demo` regenerates byte-identically instead of
carrying hand patches.

## Behaviour

1. **LICENSE.** `feathers new` writes `LICENSE` (MIT). The copyright line is the schema's
   `service.copyright`, default `"2026 Abdul-Muizz Anwar"`. `pyproject.toml` declares
   `license = "MIT"` and `license-files = ["LICENSE"]`; the Dockerfile copies `LICENSE`
   before `pip install .` (hatchling refuses to build without the declared file).
2. **Lint and types.** The generated `pyproject.toml` carries `[tool.ruff]`
   (line length 100, rules `E F I B UP N SIM RUF`, `src = ["src", "tests"]`) and
   `[tool.mypy]` (`strict = true` over `src` and `tests`); `ruff` and `mypy` are in the `dev`
   extra; the generated CI's `lint` job runs `ruff check`, `ruff format --check` and `mypy`.
   The emitted code passes all three as generated, for every schema shape below.
3. **No dead pagination code.** The repository and service emit `list_all` (offset) only
   when a `list` endpoint of that model uses `paginate: offset` or `none`, and
   `list_after` (keyset) only when one uses `paginate: cursor`; with no `list` endpoint
   neither function, nor `MAX_LIMIT`, nor the `select` import is emitted.
4. **Soft delete everywhere.** With `soft_delete: true`, a soft-deleted row is absent to
   `get`, `update`, `delete` and every list (repository `_live` is the only primary-key
   lookup). The generated per-model test proves `GET`, `PATCH` and `DELETE` answer 404
   after a `DELETE`, and the list no longer contains the row.
5. **Isolated, re-runnable tests.** A generated `tests/conftest.py` points the session at
   a fresh SQLite file under pytest's temp dir and resets the platform settings per test
   (`DEMO_MODE=false`, the test key), so a developer's `.env` cannot change outcomes and a
   second `pytest` run cannot collide with the first. `.gitignore` ignores `*.db`.
6. **Determinism.** Rendering the same schema twice is byte-identical (no dates, no
   random values, sorted imports). A golden manifest of the demo tree's SHA-256s
   (`tests/fixtures/users_demo.sha256`) makes every output change a deliberate diff;
   `FEATHERS_UPDATE_GOLDEN=1` rewrites it.

## Schema shapes exercised

- the bundled `demos/users.yaml` (UUID key, enum, soft delete, audit, cursor list);
- `offset`: an offset-paginated list and no soft delete;
- `kitchen`: integer key, `text`/`float`/`bool`/`json`/nullable fields, a custom handler,
  an `auth: none` endpoint, two models declared in non-alphabetical order;
- `bare`: no list endpoint at all, `metrics: none`, `logging: stdlib`.

## Test cases

Pass:
- `LICENSE` exists, is MIT, carries the default copyright; a schema `copyright` replaces it.
- `pyproject.toml` parses (tomllib) with the ruff/mypy tables and dev tools above, and the
  `license-files` entry names a file that exists in the tree.
- Dockerfile copies `LICENSE` and `README.md` before `pip install`.
- CI `lint` job runs ruff check, ruff format --check and mypy.
- `ruff check` and `ruff format --check` pass on every shape (fast, uses feathers' ruff).
- `mypy` (strict) and the generated `pytest` pass on the demo (slow tier, generated venv).
- cursor-only model: `list_after` present, `list_all` and `offset` absent from repository
  and service; offset-only model: the reverse; no list endpoint: neither, no `MAX_LIMIT`.
- `conftest.py` exists and `.gitignore` lists `*.db`.
- Rendering twice is byte-identical; the demo tree matches the golden manifest.

Fail / negative space:
- No generated file contains a year or timestamp other than the schema's `copyright`.
- No generated Python file has an unused import (`F401`) or unsorted imports (`I001`).
- A soft-deleted row answers 404 to `GET`, `PATCH` and `DELETE` and is not listed; a
  hard-delete model answers 404 to `GET` and `DELETE` after its delete (generated tests).
- The generated suite run twice in a row passes both times and leaves no `*.db` file in
  the project directory.
- An empty `copyright` is rejected by the schema.

## Acceptance

`make lint && make test` green in feathers; the generated demo passes its own
`ruff check`, `ruff format --check`, `mypy` and `pytest`.
