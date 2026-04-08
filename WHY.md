# Why feathers

## The obvious version

A cookiecutter template. Clone, fill in placeholders, get a FastAPI service. It works
once, for the first ten minutes of a project's life.

## Why I built it differently

Templates rot the moment you edit the generated code — you can never re-run the
generator without losing your changes. `feathers` uses `libcst` to rewrite the AST of
existing files, so `feathers add endpoint` slots new routes into your router without
touching a line you wrote. Hand-written fence markers make that contract explicit.
I weighed a simpler marker-comment approach, but it fails on anything non-trivial
(imports, decorator ordering, argument lists). Paying the libcst complexity tax buys
genuine incremental codegen, which is the difference between a toy and a tool I'd use
at work.

## What I'd change if I did it again

libcst is slow on files over a few hundred lines and its API is verbose. For a v2 I'd
split codegen into two tiers: marker-based line splicing for simple additions, AST
rewriting only when the change crosses structural boundaries.
