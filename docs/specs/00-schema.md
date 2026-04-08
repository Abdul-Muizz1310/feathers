# 00 — YAML schema validation

## Goal

Parse a YAML file describing a FastAPI service and produce a fully-validated
`ServiceSchema` Pydantic model, or raise a clear error. Generation code downstream
assumes the schema is already valid — all rejection happens here.

## Inputs / Outputs

- **Input**: `pathlib.Path` to a YAML file, OR a string of YAML content.
- **Output**: `feathers.schema.ServiceSchema` instance.
- **Failure**: `feathers.schema.SchemaError` with `message: str` and optional
  `source: Path` fields. Never raises bare `ValidationError` or `YAMLError` at the
  public surface.

## Invariants

- Every field in `ServiceSchema` has a concrete type — no `Any`.
- `ServiceSchema` is frozen (`model_config = ConfigDict(frozen=True)`) — downstream
  generators never mutate it.
- Field names within a model are unique.
- At least one model is required; endpoints may be empty.

## Test cases

### Success

- `test_parses_minimal_valid_yaml` — service + one model + empty endpoints list.
- `test_parses_full_users_demo` — the canonical `demos/users.yaml` loads and equals a
  known-good `ServiceSchema` literal.
- `test_parses_enum_field_with_values` — enum fields round-trip values list.
- `test_observability_defaults` — missing `observability` key yields prometheus/otel/structlog defaults.
- `test_deploy_defaults` — missing `deploy` key yields render/0/`/health`.

### Failure

- `test_missing_service_key` — raises `SchemaError` with `"missing required key: service"`.
- `test_missing_models_key` — raises `SchemaError` with `"missing required key: models"`.
- `test_empty_models_list` — raises `SchemaError` — must have ≥1 model.
- `test_unknown_field_type` — `type: money` → `SchemaError` mentioning the bad type.
- `test_enum_without_values` — enum field with no `values` → `SchemaError`.
- `test_duplicate_field_names` — two fields named `id` in one model → `SchemaError`.
- `test_endpoint_path_missing_leading_slash` — `path: users` → `SchemaError`.
- `test_unknown_http_method` — `method: FETCH` → `SchemaError`.
- `test_unreadable_file` — path does not exist → `SchemaError` including the path.
- `test_empty_yaml_file` — empty file → `SchemaError` with `"empty YAML"`.
- `test_malformed_yaml` — invalid YAML syntax → `SchemaError` (not `YAMLError`).

## Acceptance

- Every failure case above raises `SchemaError` with a human-readable message.
- `ServiceSchema` is frozen.
- 100% branch coverage on `schema/validators.py`.
