# codespy

A zero-dependency CLI code quality scanner for any codebase.

```
$ python3 -m codespy.cli ./my-project
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
- **Reports** — structured JSON + HTML dashboard (with Chart.js charts), Markdown tables, or CSV

## Requirements

Python 3.11+. No mandatory third-party dependencies.

Optional:
- `click` — nicer CLI experience
- `jinja2` — HTML template rendering (falls back to built-in renderer if absent)

## Usage

```bash
# Scan a directory, output HTML report
python3 -m codespy.cli ./my-project

# Markdown report
python3 -m codespy.cli ./my-project --report md --report-out summary.md

# Skip slow analyses
python3 -m codespy.cli ./my-project --no-duplication --no-smells

# Custom output paths
python3 -m codespy.cli ./my-project --output-json results.json --report-out dashboard.html

# Install as a command (optional)
pip install -e .
codespy ./my-project
```

### All flags

| Flag | Default | Description |
|---|---|---|
| `PATH` | required | Directory or file to scan |
| `--output-json PATH` | `report.json` | JSON output path |
| `--report html\|md\|csv` | `html` | Report format |
| `--report-out PATH` | `report.<ext>` | Report output path |
| `--no-complexity` | off | Skip cyclomatic complexity |
| `--no-duplication` | off | Skip duplication analysis |
| `--no-smells` | off | Skip smell detection |
| `--ignore PATTERN` | — | Extra dirs/patterns to ignore (repeatable) |
| `-q / --quiet` | off | Suppress progress output |
| `--version` | — | Print version |

## Project structure

```
codespy/
├── cli.py           — Entry point
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
├── fixtures/        — Small Python files used as test inputs
├── test_metrics.py
├── test_complexity.py
├── test_smells.py
├── test_duplication.py
└── test_quality.py
```

## Running tests

```bash
python3 -m unittest discover tests/ -v
```

## Architecture

See [DESIGN.md](DESIGN.md) for key architectural decisions and trade-offs.
