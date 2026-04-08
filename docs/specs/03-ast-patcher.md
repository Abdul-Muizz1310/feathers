# 03 — libcst AST patcher (incremental mode)

## Goal

Given an existing generated service and an updated `ServiceSchema`, add new endpoints
and models without touching hand-written code. This is what makes feathers not a
cookiecutter.

## Inputs / Outputs

- **Input**: service directory on disk + new `ServiceSchema`.
- **Output**: modified files on disk. Returns list of `(path, action)` tuples where
  `action ∈ {"added", "unchanged"}`.

## Invariants

- **Idempotent**: running twice with the same schema against the same service is a no-op.
- **Hand-written fences**: code between `# feathers: begin hand-written` and
  `# feathers: end hand-written` (Python) is **never** touched.
- **Existing code preserved**: endpoint additions insert a new function after the
  last existing function in the router file; existing imports are merged, not rewritten.
- **Import ordering**: new imports inserted at top, alphabetically within their group.

## Test cases

### Add endpoint — success

- `test_adds_new_endpoint_function` — base router has one function; after add, has two;
  first function byte-identical.
- `test_merges_imports` — new endpoint needs `from uuid import UUID`; import is added
  at top, existing imports untouched.
- `test_idempotent_add_endpoint` — run `add_endpoint` twice with same schema; second
  call reports all endpoints `"unchanged"`; file bytes identical between runs.
- `test_preserves_hand_written_fence` — inject a `# feathers: begin/end hand-written`
  block with custom code inside the router; after add, block is untouched byte-for-byte.

### Add model — success

- `test_adds_new_model_class` — appends a class to `models/<m>.py`, existing classes
  untouched.
- `test_add_model_is_idempotent` — second run is a no-op.

### Failure

- `test_add_to_nonexistent_service_raises` — target dir missing → `PatcherError`.
- `test_add_invalid_schema_raises` — `SchemaError` propagates.

## Acceptance

- Snapshot test green: `feathers add endpoint` on a freshly generated service with the
  same schema produces zero diff.
- Hand-written fence test green.
- Adding a model generates a stub `alembic` migration file with a new timestamped
  filename — existing migrations untouched. (Content is a placeholder for v0.1.0;
  actual autogenerate is deferred.)
