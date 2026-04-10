# CodeSpy — Ground Rules

## 1. Read before modifying

Always read the relevant source file before suggesting changes. The module boundaries are intentional — `scanner.py` orchestrates, analyzers are stateless functions, reporters are output-only. Don't mix concerns.

## 2. Preserve the single-pass invariant

Each file is read exactly once in `metrics.count_lines()`. All downstream analyzers receive `source_lines: list[str]` — they must NOT re-open or re-read the file. If a new analyzer needs the source, it gets it from the `source_map` dict passed by `scanner.py`.

## 3. Test against fixtures, not generated strings

Unit tests live in `tests/` and use the fixture files in `tests/fixtures/`. When adding a new analyzer or changing behavior, verify against the real fixture files. Don't test only with hand-crafted inline strings that miss edge cases.

## 4. Keep dependencies optional

`codespy` must run with zero third-party packages. `click` and `jinja2` are optional — check with `try: import click` before using. Any new optional dependency must have a fallback path using stdlib only.

## 5. Dataclasses, not dicts, for results

All analysis results use typed dataclasses from `models.py`. Don't return bare `dict` objects from analyzers. This keeps the JSON reporter trivial (`dataclasses.asdict`) and the code self-documenting.

---

## Part II — Refactor Loop rules

## 6. The refactor-loop command is the feedback loop

`/refactor-loop <path>` is the standard workflow for refactoring. Always use it instead of ad-hoc refactoring. It finds the target, proposes the fix, and verifies via re-scan — no manual complexity checks needed.

## 7. The scanner is the proof — always re-scan after refactoring

Never declare a refactor "done" without re-running `python3 -m codespy.cli target <file>` and confirming the CC dropped. The success signal is `function_cc` drops ≥ 2 points or falls below 10. If the scanner doesn't confirm it, it didn't work.

## 8. One function per loop iteration

Refactor one function at a time. After each verified improvement, run the loop again to find the next target. Don't batch multiple refactors into one step — it makes the feedback signal ambiguous.

## 9. `tests/fixtures/complex.py` is the canonical demo target

`parse_token` in `complex.py` has CC=22, too_many_args (7 params), and deep nesting. It is the standard target for demonstrating the refactor loop. Always use it for fresh-session tests unless a real project is available.

## 10. Preserve public interfaces during refactoring

Helper functions extracted during refactoring should be private (prefixed `_`). The original function's signature and return type must not change unless the user explicitly agrees. Tests must not be modified.
