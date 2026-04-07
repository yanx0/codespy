# CodeSpy — Architecture & Design Decisions

## Overview

CodeSpy is a zero-mandatory-dependency CLI code scanner written in Python 3.11+. It analyzes any codebase and reports on code quality via JSON output and a human-readable HTML/Markdown/CSV report.

## Architecture

```
codespy/
├── cli.py           — Entry point: CLI flags → ScanConfig → scan() → reporters
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
    ├── html_reporter.py — HTML dashboard with Chart.js visualizations
    └── md_reporter.py   — Markdown tables
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

**Trade-off:** Near-duplicates that differ in every line (e.g., copy-paste with variable renaming throughout) won't be detected. The algorithm catches structural copy-paste, not refactored copies. This is a reasonable scope for a v1 tool.

### Decision 5: Dataclasses throughout

All intermediate results are typed dataclasses, not dicts. The JSON reporter trivially uses `dataclasses.asdict`. The code is self-documenting without type annotation comments.

**Trade-off:** Python 3.7+ required. No issue given the 3.11+ baseline.

### Decision 6: Pluggable reporters, no plugin architecture

Three concrete reporter classes (`json_reporter`, `html_reporter`, `md_reporter`) rather than an ABC + dynamic loading. Adding a fourth reporter is a 20-line addition. Zero framework overhead.

**Trade-off:** No runtime extensibility. Accepted — over-engineering for a CLI tool.

## Analysis Features Selected

| Feature | Why chosen |
|---|---|
| Cyclomatic complexity | Highest signal for maintainability; works precisely for Python via AST |
| Code smell detection | 6 practical smell types; fast; no AST required for most |
| Code duplication | Complementary to the above; hash-first makes it fast |

Together they cover three orthogonal quality dimensions: complexity (hard to understand), smell (bad structure), and duplication (copy-paste debt). Each feeds a sub-score in the quality model.

## Quality Scoring Model

```
composite = complexity_score * 0.40 + smell_score * 0.35 + duplication_score * 0.25
```

- **Complexity score**: `100 - (avg_complexity - 1) * 8`, minus 3 points per hotspot (≥10 CC), clamped 0–100
- **Smell score**: `100 - (weighted_smells_per_100_lines * 3)`, clamped 0–100; `todo_fixme` weighted 0.2×
- **Duplication score**: `100 - (duplication_percent * 5)`, clamped 0–100

Grades: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F < 60.

## Extension Points

- **New language**: Add entry to `EXTENSION_MAP` and `COMMENT_SYNTAX` in `languages.py`
- **New smell type**: Add detection logic in `analyzers/smells.py`, add description in `html_reporter.py`
- **New reporter format**: Add `<format>_reporter.py` in `reporters/`, wire up in `cli.py`
- **New analyzer**: Add module in `analyzers/`, call it in `scanner.py`, add result field to `FileResult`
