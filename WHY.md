# Why feathers

## The obvious version

A cookiecutter template. Clone, fill in placeholders, get a FastAPI service. It works
once, for the first ten minutes of a project's life.

## Why I built it differently

Templates rot the moment you edit the generated code, and most scaffolders trust their
input. `feathers` does the opposite on both counts. The schema is a frozen Pydantic v2
model tree, so a malformed YAML is rejected with a precise, located error before a single
file is written — illegal states never reach the renderer. The codegen is then idempotent
and fence-protected: `feathers add endpoint` splices new handler functions in by locating
deterministic `# feathers:` marker comments and inserting above the hand-written fence,
guarded by a function-existence check. Running it twice is a byte-identical no-op, and code
between the fences is never touched. This is deterministic marker splicing, not AST
rewriting. I weighed parsing each file into a concrete syntax tree, but for v0.1 the
additions are append-only, so a syntax tree buys correctness I do not yet need at a cost in
speed and dependencies.

## Scope (stated limitations, unchanged in 0.2)

`feathers` generates **single-table models only**. The schema has no
reference/foreign-key field kind, so a model cannot declare a relationship to
another model — every model becomes an isolated SQLAlchemy table with no
`ForeignKey`/`relationship()`. One-to-many and many-to-many (e.g. `User` ->
`Order`) are deliberately out of scope and remain the headline feature for a
later release (a `type: ref` field emitting the FK column plus the
`relationship()` on both sides); 0.2 spent its scope on the platform token
contract and on making the generated project lint-, type- and test-clean. Until then, add cross-model relations by hand
inside the generated model files (they are yours to edit — regeneration never
clobbers hand-written code between the fences).

Auth fails closed. Every generated route except the platform routes and
endpoints declared `auth: none` requires a bastion-signed token for this
service's id (platform token contract v2); per-endpoint `auth:` roles are then
enforced by the `require_role` dependency the router wires from each endpoint's
declared role. With no bastion key configured those routes answer 503 instead of
serving anyone, and `DEMO_MODE` (off by default) only tolerates a *missing* token
during a rollout — it never accepts an invalid one (see `core/platform_token.py`).
v0.1 failed open here; 0.2 reversed that.

## What I'd change if I did it again

Marker splicing cannot merge imports — once a handler needs a new import, I hand-edit it.
For v0.2 I would add a CST-based patcher (libcst) scoped only to import merging, where a
real parse genuinely earns its keep.
