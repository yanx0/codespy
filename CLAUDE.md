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
