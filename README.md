# codespy

A zero-dependency CLI code quality scanner — and AI-powered refactoring assistant — for any codebase.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/yanx0/codespy.git
cd codespy
pip install -e .

# 2. Scan a project
codespy ./my-project
# → opens report.html + report.json in the current directory

# 3. Find the worst function to refactor
codespy target ./my-project
```

> **On macOS with Homebrew Python**, `pip install` may fail with "externally-managed-environment".
> Use one of these instead:
> ```bash
> # Option A — install anyway (simplest)
> pip install -e . --break-system-packages
>
> # Option B — virtual environment (cleaner)
> python3 -m venv .venv && source .venv/bin/activate
> pip install -e .
> ```

After install, verify it works:

```bash
codespy --version   # codespy, version 0.1.0
codespy tests/fixtures --no-duplication -q
# → Quality score: .../100 (Grade .)
```

---

## Features

- **Language detection** — 50+ file extensions
- **Metrics** — lines of code, comments, blanks, function & class counts
- **Cyclomatic complexity** — AST-precise for Python, regex-based for everything else; flags hotspots ≥ 10
- **Code smell detection** — long functions, too many parameters, deep nesting, magic numbers, long files, TODO/FIXME markers
- **Duplication analysis** — hash-first block matching + similarity scoring across all files
- **Quality score** — 0–100 composite with letter grade (A–F), three sub-scores
- **Reports** — editorial-style HTML dashboard (Chart.js), Markdown tables, or CSV
- **Refactor target** — `codespy target` finds the highest-priority function to fix, outputs a machine-readable JSON action plan
- **Refactor loop** — `/refactor-loop` Claude command drives a scan → propose → apply → re-scan feedback loop

## Requirements

Python 3.11+. No mandatory third-party dependencies.

Optional (auto-detected):
- `click` — nicer CLI experience
- `jinja2` — HTML template rendering (falls back to built-in renderer if absent)

---

## Usage

### Scan

```bash
# Scan a directory, output HTML report (default)
codespy ./my-project

# "scan" keyword is also accepted
codespy scan ./my-project

# Markdown report
codespy ./my-project --report md --report-out summary.md

# Skip slow analyses (useful for large repos)
codespy ./my-project --no-duplication --no-smells

# Exclude paths by glob (repeatable)
codespy ./my-project --exclude "*/migrations/*" --exclude "*/vendor/*"

# Custom output paths
codespy ./my-project --output-json results.json --report-out dashboard.html
```

Reports are written to the **current directory**, not the scanned directory.

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

Launch Claude Code **from inside the `codespy` directory** (commands are loaded at startup):

```bash
cd ~/codespy
claude
```

Then in the Claude Code session:

```
/refactor-loop ./my-project
```

Claude will find the target, propose a concrete diff, apply it on approval, and re-scan to verify the complexity dropped. See `.claude/commands/refactor-loop.md` for the full workflow spec.

> **Note:** If you see `Unknown skill: refactor-loop`, you launched Claude Code from a different directory. Exit and relaunch from inside `~/codespy`.

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

---

## Troubleshooting

**`zsh: command not found: codespy`**
You haven't installed the package yet, or the install target isn't on your PATH. Run `pip install -e . --break-system-packages` from the repo root, then open a new terminal.

**`Error: Got unexpected extra argument (/path)`**
This was a bug in older versions where `codespy scan <path>` wasn't recognized. Update to the latest version (`git pull && pip install -e .`). Both `codespy <path>` and `codespy scan <path>` now work.

**`Unknown skill: refactor-loop`**
Claude Code loads custom commands from `.claude/commands/` at startup. If you launched Claude Code from a parent directory and then `cd codespy`, the commands won't be found. Exit and relaunch: `cd ~/codespy && claude`.

**`python3 -m pytest` fails with "No module named pytest"**
pytest isn't installed in your active Python environment. Either activate the venv (`. .venv/bin/activate`) or install pytest: `pip install pytest --break-system-packages`.

**Duplication shows > 100%**
This was a bug in early versions — duplicate line counting summed pair ranges instead of counting unique lines. Fixed in the current version.

---

## Running tests

```bash
# With venv (recommended)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python3 -m pytest tests/ -v

# Without venv (if pytest is already installed)
python3 -m pytest tests/ -v
```

Expected output: `21 passed`.

---

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
└── test_*.py
.claude/
└── commands/
    └── refactor-loop.md   — Claude Code slash command
```

## Architecture

See [DESIGN.md](DESIGN.md) for key architectural decisions and trade-offs.
