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

## Scope in v0.1 (stated limitations)

`feathers` v0.1 generates **single-table models only**. The schema has no
reference/foreign-key field kind, so a model cannot declare a relationship to
another model — every model becomes an isolated SQLAlchemy table with no
`ForeignKey`/`relationship()`. One-to-many and many-to-many (e.g. `User` ->
`Order`) are deliberately out of scope for v0.1 and are the headline feature
planned for v0.2 (a `type: ref` field emitting the FK column plus the
`relationship()` on both sides). Until then, add cross-model relations by hand
inside the generated model files (they are yours to edit — regeneration never
clobbers hand-written code between the fences).

Per-endpoint `auth:` roles ARE enforced (via the `require_role` dependency the
router wires from each endpoint's declared role), but only when the platform is
running with `DEMO_MODE=false` **and** a bastion public key is configured;
otherwise enforcement fails open by design (see `core/platform_token.py`).

## What I'd change if I did it again

Marker splicing cannot merge imports — once a handler needs a new import, I hand-edit it.
For v0.2 I would add a CST-based patcher (libcst) scoped only to import merging, where a
real parse genuinely earns its keep.
