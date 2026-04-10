# CodeSpy — Architecture & Design Decisions

## Overview

CodeSpy is a zero-mandatory-dependency CLI code scanner written in Python 3.11+. It analyzes any codebase and reports on code quality via JSON output and an editorial-style HTML/Markdown/CSV report. It also includes a `target` subcommand and a Claude Code slash command that together form a scanner-driven refactoring feedback loop.

## Architecture

```
codespy/
├── cli.py           — Entry point: scan + target subcommands → reporters
├── scanner.py       — Orchestrates traversal + per-file analysis pipeline
├── languages.py     — Extension → language map; comment syntax; ignore patterns
├── metrics.py       — LOC counting (single-pass); function/class counting
├── models.py        — Dataclasses for all result types (FileResult, ScanResult, etc.)
├── quality.py       — 0–100 composite scoring with letter grade
├── analyzers/
│   ├── complexity.py  — Cyclomatic complexity (AST for Python, regex for others)
│   ├── smells.py      — Code smell detection (6 smell types)
│   └── duplication.py — Hash-first block deduplication + SequenceMatcher
└── reporters/
    ├── json_reporter.py — JSON serialization
    ├── html_reporter.py — Editorial HTML dashboard with Chart.js
    └── md_reporter.py   — Markdown tables
.claude/
└── commands/
    └── refactor-loop.md — Claude Code slash command (6-step refactor workflow)
```

## Key Decisions

### Decision 1: Zero mandatory dependencies

`ast`, `re`, `difflib`, `hashlib`, `pathlib`, `json` — all stdlib. `click` and `jinja2` are used when present but gracefully degraded. This means `codespy` runs anywhere Python 3.11+ is installed with no `pip install` required.

**Trade-off:** The HTML report is slightly less polished without jinja2, but jinja2 is so universally available it rarely matters.

### Decision 2: Single-pass file reading

`metrics.py` reads each file exactly once and returns `(code, comments, blanks, source_lines[])`. All downstream analyzers receive the in-memory `source_lines` list — no re-reading files.

**Trade-off:** Holds all source lines in memory simultaneously. For a 100k-line project that's ~5MB — well within reason. Streaming would complicate the API with no real benefit at this scale.

### Decision 3: AST for Python, regex fallback for everything else

Python's `ast` module is precise: it handles string literals that look like comments, multiline expressions, decorators. For JS/TS/Go/Java/etc., regex over line-split text is ~95% accurate and orders of magnitude simpler to maintain.

**Trade-off:** Non-Python complexity scores are approximate. This is documented in the report output.

### Decision 4: Hash-first duplication (not O(n²) difflib)

Building a hash index of 6-line normalized windows is O(total_lines). Only hash collisions — blocks with identical content — become candidates for `SequenceMatcher`. This keeps duplication analysis sub-second even on 50k-line repos.

Duplicate line counting uses unique `(file, line_number)` tuples so a line shared between N partners is counted once, not N times. This prevents duplication percentages from exceeding 100%.

**Trade-off:** Near-duplicates that differ in every line (e.g., copy-paste with variable renaming throughout) won't be detected. The algorithm catches structural copy-paste, not refactored copies.

### Decision 5: Dataclasses throughout

All intermediate results are typed dataclasses, not dicts. The JSON reporter trivially uses `dataclasses.asdict`. The code is self-documenting without type annotation comments.

### Decision 6: Pluggable reporters, no plugin architecture

Three concrete reporter classes rather than an ABC + dynamic loading. Adding a fourth reporter is a 20-line addition. Zero framework overhead.

### Decision 7: `codespy target` as a machine-readable subcommand

The `target` subcommand outputs a single JSON object with `file`, `function`, `function_cc`, `action`, and `success_signal` — designed for tool consumption, not human reading. This makes it composable with Claude Code commands, CI scripts, and other tooling.

The target is selected by per-file risk scoring:
- Complexity: 40% (max CC / 20, capped at 1.0)
- Smells: 35% (smell count / 10, capped at 1.0)
- Duplication: 15% (1.0 if file appears in any dup pair, else 0)
- Size: 10% (code_lines / 400, capped at 1.0)

A file must have at least one hotspot (CC ≥ 10) or two non-trivial smells to qualify as a target.

### Decision 8: Scanner-as-proof refactoring loop

The refactor loop (`.claude/commands/refactor-loop.md`) uses the scanner as the verification signal rather than code review. The success criterion is binary: `function_cc` drops ≥ 2 points or falls below 10 on re-scan. This removes ambiguity from "did the refactor work?" and makes the feedback loop deterministic.

**Trade-off:** CC is a necessary but not sufficient quality signal — it doesn't measure readability or test coverage. Accepted as the right trade-off for an automated loop.

### Decision 9: Manual `target` pre-routing in `main()`

Rather than using a click Group (which would break the existing `codespy <path>` invocation), `main()` manually pre-routes the `target` subcommand before click sees `sys.argv`. This preserves full backwards compatibility.

### Decision 10: Editorial HTML style

The HTML dashboard uses a light editorial aesthetic (white background, Georgia serif headlines, two-column annotation cards with blue left border) rather than a dark dashboard style. More legible in print and in code review contexts.

## Analysis Features

| Feature | Why chosen |
|---|---|
| Cyclomatic complexity | Highest signal for maintainability; works precisely for Python via AST |
| Code smell detection | 6 practical smell types; fast; no AST required for most |
| Code duplication | Complementary to the above; hash-first makes it fast |

## Quality Scoring Model

```
composite = complexity_score * 0.40 + smell_score * 0.35 + duplication_score * 0.25
```

- **Complexity score**: `100 - (avg_complexity - 1) * 8`, minus 3 points per hotspot (CC ≥ 10), clamped 0–100
- **Smell score**: `100 - (weighted_smells_per_100_lines * 3)`, clamped 0–100; `todo_fixme` weighted 0.2×
- **Duplication score**: `100 - (duplication_percent * 5)`, clamped 0–100

Grades: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F < 60.

## Default Ignore Patterns

`scanner.py` skips these directories by default: `.git`, `__pycache__`, `.venv`, `venv`, `node_modules`, `dist`, `build`, `target`, `dbt_packages`. Additional paths can be excluded via `--exclude GLOB` (e.g., `--exclude "*/migrations/*"`).

## Extension Points

- **New language**: Add entry to `EXTENSION_MAP` and `COMMENT_SYNTAX` in `languages.py`
- **New smell type**: Add detection logic in `analyzers/smells.py`, wire label in `html_reporter.py`
- **New reporter format**: Add `<format>_reporter.py` in `reporters/`, wire up in `cli.py`
- **New analyzer**: Add module in `analyzers/`, call it in `scanner.py`, add result field to `FileResult`
- **New Claude command**: Add `.md` file to `.claude/commands/` — Claude Code auto-discovers it
