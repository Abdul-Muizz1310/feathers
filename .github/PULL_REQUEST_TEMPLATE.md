# PR

## Summary

<!-- What changed and why. One paragraph. -->

## Spec-TDD checklist

- [ ] Spec written under `docs/specs/` with inputs, outputs, invariants, and enumerated test cases (success **and** failure paths)
- [ ] Red tests committed first with message `test: red tests for <feature>`
- [ ] Production code added only to turn those tests green
- [ ] Every enumerated failure case is covered by a test
- [ ] Coverage ≥80% on changed files in `src/`
- [ ] Ruff + mypy clean
- [ ] Self-review against acceptance criteria in the spec file — every box checked

## Notes

<!-- Tradeoffs, follow-ups, anything a reviewer should know. -->
