# CodeSpy — Ground Rules

## 1. Read before modifying. Respect module boundaries.

Read the relevant file before suggesting any change. `scanner.py` orchestrates, analyzers are stateless, reporters are output-only. Don't mix concerns across those layers.

## 2. Preserve the single-pass invariant.

Each file is read exactly once in `metrics.count_lines()`. All downstream analyzers receive `source_lines: list[str]` — they must never re-open the file. New analyzers get source from the `source_map` dict passed by `scanner.py`.

## 3. Use typed dataclasses for all results. Keep dependencies optional.

Return typed dataclasses from `models.py`, not bare dicts. `click` and `jinja2` are optional — any new dependency must have a stdlib fallback. The tool must run with zero installs.

## 4. Test against fixture files, not generated strings.

Tests live in `tests/` and use `tests/fixtures/`. Verify new analyzers and behavior changes against real fixture files — inline strings miss edge cases.

## 5. The scanner is the proof. One function per loop iteration.

Never declare a refactor done without re-running `codespy target <file>` and confirming `function_cc` dropped ≥ 2 points or fell below 10. Refactor one function per iteration — batching makes the signal ambiguous. Extracted helpers should be private (`_`). The original function's signature must not change without explicit agreement.
