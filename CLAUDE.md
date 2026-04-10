# CodeSpy — Ground Rules

## 1. Read before modifying. Respect module boundaries.

Read the relevant file before suggesting any change. `scanner.py` orchestrates, analyzers are stateless, reporters are output-only. Don't mix concerns across those layers.

## 2. Preserve the single-pass invariant.

Each file is read exactly once in `metrics.count_lines()`. All downstream analyzers receive `source_lines: list[str]` — they must never re-open the file. New analyzers get source from the `source_map` dict passed by `scanner.py`.

## 3. Use typed dataclasses for all results. Keep dependencies optional.

Return typed dataclasses from `models.py`, not bare dicts. `click` and `jinja2` are optional — any new dependency must have a stdlib fallback. The tool must run with zero installs.

## 4. Test against fixture files, not generated strings.

Tests live in `tests/` and use `tests/fixtures/`. Verify new analyzers and behavior changes against real fixture files — inline strings miss edge cases.

---

## 5. Refactor Assistant Policy

These rules govern all refactoring done via `/refactor-loop` or any AI-assisted change.

### Prefer the smallest meaningful refactor.

Default to the smallest change that produces a measurable improvement. Do not pursue a cleaner redesign when a smaller, safer edit achieves enough improvement at lower risk.

Prefer these refactor types, in order of risk:
1. Add guard clauses / early returns to flatten nesting
2. Extract a private helper for a distinct logical step
3. Replace magic numbers with named constants
4. Isolate repeated expressions or conditional branches

Avoid restructuring module boundaries, changing control flow across functions, or introducing new abstractions unless the gain clearly justifies it.

### Always compare two options before proposing.

For every refactor, consider:
- **Option A** — minimal: the smallest change that moves the needle
- **Option B** — larger: a cleaner restructure with better long-term shape

Recommend Option A by default. Switch to Option B only if it has clearly better payoff for similar or lower risk. Always state which option you are recommending and why.

### Explain the trade-off for every proposal.

Each proposal must include:
- Expected CC drop or smell reduction
- Estimated lines changed and functions touched
- Risk level (low / medium / high) and what makes it risky
- Why this is the best balance of improvement vs. change size

### Keep the change budget small.

One function per iteration. Stay within one file. If the change starts growing — touching multiple functions, introducing new state, or crossing file boundaries — stop and ask before continuing.

### Preserve interfaces and behavior.

Do not change public function signatures, return types, module boundaries, or tests. Extracted helpers must be private (prefixed `_`). The original function's external behavior must remain identical.

### The scanner is the proof.

A refactor is not done until `codespy target <file>` confirms improvement. The success signal is:
- `function_cc` drops by ≥ 2 points, **or**
- `function_cc` falls below 10

If the scanner does not confirm it, the refactor did not succeed — regardless of how the code looks.
