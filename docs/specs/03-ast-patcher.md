# 03 — marker-based patcher (incremental mode)

## Goal

Given an existing generated service and an updated `ServiceSchema`, add new endpoints
and models without touching hand-written code. This is what makes feathers not a
cookiecutter.

## Inputs / Outputs

- **Input**: service directory on disk + new `ServiceSchema`.
- **Output**: modified files on disk. Returns list of `(path, action)` tuples where
  `action ∈ {"added", "unchanged"}`.

## Approach

This is deterministic marker-based splicing, not AST rewriting. Generated router files
carry `# feathers:` fence comments. `add_endpoint` reads the source as text, decides
whether a handler already exists with a function-existence check (a `^async def <name>`
regex match), and inserts a new handler function above the hand-written fence — or appends
it when no fence is present. `add_model` writes a `@dataclass` stub for any model that does
not yet have a file. No concrete syntax tree is parsed and `libcst` is not used.

## Invariants

- **Idempotent**: running twice with the same schema against the same service is a no-op
  (byte-identical output on the second run).
- **Hand-written fences**: code between `# feathers: begin hand-written` and
  `# feathers: end hand-written` (Python) is **never** touched.
- **Insertion point**: a new handler is spliced in directly above the hand-written fence
  when one is present; otherwise it is appended to the end of the router file.
- **Function-existence check**: a handler is added only when no `async def` of the same
  name already exists, which is what makes re-runs no-ops.

## Test cases

### Add endpoint — success

- `test_adds_new_endpoint_function` — base router has one function; after add, the new
  handler is present and the file changed.
- `test_idempotent_add_endpoint` — run `add_endpoint` twice with same schema; second
  call reports all endpoints `"unchanged"`; file bytes identical between runs.
- `test_preserves_hand_written_fence` — inject a `# feathers: begin/end hand-written`
  block with custom code inside the router; after add, the block is preserved.

### Add model — success

- `test_adds_new_model_class` — writes a `@dataclass` stub file at `models/<m>.py` for a
  model that does not yet have one.
- `test_add_model_is_idempotent` — second run is a no-op.

### Failure

- `test_add_to_nonexistent_service_raises` — target dir missing → `PatcherError`.
- `test_add_endpoint_missing_routers_dir_raises` — service dir exists but has no routers
  dir → `PatcherError`.
- `test_add_model_to_nonexistent_service_raises` — `add_model` target dir missing →
  `PatcherError`.

## Acceptance

- Snapshot test green: `feathers add endpoint` on a freshly generated service with the
  same schema produces zero diff.
- Hand-written fence test green.
- Adding a model writes a `@dataclass` stub at `models/<m>.py` for any model that lacks a
  file; existing model files are left untouched. SQLAlchemy and Alembic wiring is deferred
  to v0.2.
