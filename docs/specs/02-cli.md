# 02 — Typer CLI

## Goal

Expose the feathers functionality as a Typer app with subcommands `new`, `add endpoint`,
`add model`, `lint`, `doctor`. (`bench` exists in the spec but is deferred past v0.1.0 —
see Acceptance.)

## Inputs / Outputs

- Invoked via `feathers` or `python -m feathers`.
- Exit codes: `0` on success, `1` on schema/IO error, `2` on usage error (Typer default).

## Test cases

### Success

- `test_new_creates_service_dir` — `feathers new --schema <users> --name hello_users --out <tmp>`
  creates `<tmp>/hello_users/` with at least `pyproject.toml`, `README.md`, `src/hello_users/main.py`.
- `test_lint_valid_yaml_exit_zero` — `feathers lint <users>` exits 0, stdout contains `"ok"`.
- `test_doctor_runs` — `feathers doctor` exits 0 regardless of environment,
  reports Python version.
- `test_root_help` — `feathers --help` exits 0, mentions `new`, `add`, `lint`, `doctor`.
- `test_new_help` — `feathers new --help` exits 0, shows `--schema`, `--name`, `--out`, `--force`.
- `test_new_with_force_overwrites` — pre-create target, `--force` succeeds.

### Failure

- `test_new_refuses_overwrite_without_force` — pre-create target, no `--force` → exit 1,
  stderr mentions the path.
- `test_lint_invalid_yaml_exit_one` — invalid schema file → exit 1, stderr has error message.
- `test_new_missing_schema_file` — non-existent `--schema` path → exit 1.
- `test_new_missing_required_args` — missing `--schema` → exit 2 (Typer usage error).

## Acceptance

- `feathers --help` runs in <500 ms.
- All commands tested via Typer's `CliRunner`, no subprocess fork.
- `bench` is wired in the Typer tree but raises `NotImplementedError` with message
  `"feathers bench is coming in v0.2"` (covered by a test asserting that).
- `add endpoint` and `add model` are fully implemented — see `03-ast-patcher.md`.
