# codespy

A zero-dependency CLI code quality scanner — and AI-powered refactoring assistant — for any codebase.

```
$ codespy ./my-project
Scanning 42 files in /path/to/my-project...
Analyzed 38 source files.
Quality score: 74/100 (Grade C)
JSON report: report.json
Report (html): report.html
```

## Features

- **Language detection** — 50+ file extensions
- **Metrics** — lines of code, comments, blanks, function & class counts
- **Cyclomatic complexity** — AST-precise for Python, regex-based for everything else; flags hotspots ≥ 10
- **Code smell detection** — long functions, too many parameters, deep nesting, magic numbers, long files, TODO/FIXME markers
- **Duplication analysis** — hash-first block matching + similarity scoring across all files
- **Quality score** — 0–100 composite with letter grade (A–F), three sub-scores
- **Reports** — editorial-style HTML dashboard (Chart.js), Markdown tables, or CSV
- **Refactor target** — `codespy target` finds the highest-priority function to fix and emits a machine-readable JSON action plan
- **Refactor loop** — `/refactor-loop` Claude command drives a scan → propose → apply → re-scan feedback loop

## Requirements

Python 3.11+. No mandatory third-party dependencies.

Optional:
- `click` — nicer CLI experience
- `jinja2` — HTML template rendering (falls back to built-in renderer if absent)

## Install

```bash
pip install -e .
```

## Usage

### Scan

```bash
# Scan a directory, output HTML report
codespy ./my-project

# "scan" keyword is also accepted
codespy scan ./my-project

# Markdown report
codespy ./my-project --report md --report-out summary.md

# Skip slow analyses
codespy ./my-project --no-duplication --no-smells

# Exclude files by glob
codespy ./my-project --exclude "*/migrations/*" --exclude "*/vendor/*"

# Custom output paths
codespy ./my-project --output-json results.json --report-out dashboard.html
```

### Find the top refactoring target

```bash
codespy target ./my-project
```

Outputs JSON with the highest-priority file and function:

```json
{
  "file": "src/parser.py",
  "function": "parse_token",
  "function_cc": 22,
  "risk_label": "HIGH",
  "action": "Refactor `parse_token` — cyclomatic complexity 22 (target: below 10)",
  "success_signal": "Re-scan shows `parse_token` CC drops by ≥2 points or falls below 10"
}
```

### Refactor loop (Claude Code)

With [Claude Code](https://claude.ai/code) installed and launched from this repo:

```
/refactor-loop ./my-project
```

Claude will find the target, propose a concrete diff, apply it on approval, and re-scan to verify the complexity dropped. See `.claude/commands/refactor-loop.md` for the full workflow spec.

### All scan flags

| Flag | Default | Description |
|---|---|---|
| `PATH` | required | Directory or file to scan |
| `--output-json PATH` | `report.json` | JSON output path |
| `--report html\|md\|csv` | `html` | Report format |
| `--report-out PATH` | `report.<ext>` | Report output path |
| `--no-complexity` | off | Skip cyclomatic complexity |
| `--no-duplication` | off | Skip duplication analysis |
| `--no-smells` | off | Skip smell detection |
| `--exclude GLOB` | — | Exclude files matching glob (repeatable) |
| `--ignore PATTERN` | — | Extra dir names to ignore (legacy, repeatable) |
| `-q / --quiet` | off | Suppress progress output |
| `--version` | — | Print version |

Default ignored directories: `.git`, `__pycache__`, `.venv`, `venv`, `node_modules`, `dist`, `build`, `target`, `dbt_packages`.

## Project structure

```
codespy/
├── cli.py           — Entry point; scan + target subcommands
├── scanner.py       — Traversal + analysis orchestration
├── languages.py     — Language detection, comment syntax, ignore patterns
├── metrics.py       — LOC counting, function/class extraction
├── models.py        — Result dataclasses
├── quality.py       — 0–100 scoring model
├── analyzers/
│   ├── complexity.py
│   ├── smells.py
│   └── duplication.py
└── reporters/
    ├── json_reporter.py
    ├── html_reporter.py
    └── md_reporter.py
tests/
├── fixtures/        — Small source files used as test inputs
├── test_metrics.py
├── test_complexity.py
├── test_smells.py
├── test_duplication.py
└── test_quality.py
.claude/
└── commands/
    └── refactor-loop.md   — Claude Code slash command
```

## Running tests

```bash
python3 -m pytest tests/
```

## Architecture

See [DESIGN.md](DESIGN.md) for key architectural decisions and trade-offs.
