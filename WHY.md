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

## What I'd change if I did it again

Marker splicing cannot merge imports — once a handler needs a new import, I hand-edit it.
For v0.2 I would add a CST-based patcher (libcst) scoped only to import merging, where a
real parse genuinely earns its keep.
