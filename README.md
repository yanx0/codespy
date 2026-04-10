# CodeSpy

**Scan. Prioritize. Refactor. Re-scan.**

CodeSpy measures complexity, smells, and duplication across any codebase, then surfaces the highest-risk function as a structured target. The included `/refactor-loop` Claude command proposes a concrete fix, applies it on approval, and re-scans to show you the before/after — no guessing whether the refactor helped.

---

## Why CodeSpy

Technical debt is rarely evenly distributed. One function with cyclomatic complexity 22 is worth more attention than thirty minor style issues — but most scanners treat them as equals and dump a flat list.

CodeSpy is built around a different model:

| Step | Command | Output |
|---|---|---|
| **Measure** | `codespy ./project` | Editorial HTML dashboard, 0–100 quality score, risk-ranked file list |
| **Prioritize** | `codespy target ./project` | Single highest-risk function as machine-readable JSON |
| **Refactor** | `/refactor-loop` in Claude Code | Concrete diff proposed, applied on approval |
| **Verify** | Auto re-scan | Scanner confirms CC dropped ≥ 2 points or fell below 10 |

The success signal is binary and scanner-verified — not a code review opinion.

---

## Quick Start

```bash
git clone https://github.com/yanx0/codespy.git
cd codespy

# Create a virtual environment (recommended — avoids system Python conflicts)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

codespy ./my-project        # scan → generates report.html + report.json
codespy target ./my-project # find the highest-priority function to fix
```

The HTML report opens automatically in your default browser on macOS and most desktop Linux environments. Use `--no-open` to suppress this, or `-q` for fully quiet output.

---

## The Refactor Loop

The standout feature. Launch Claude Code from the repo root and run:

```
/refactor-loop ./my-project
```

Claude will:
1. Run `codespy target` to find the highest-risk function
2. Read the function and propose a concrete refactoring with a diff
3. Apply the edit on your approval
4. Re-scan and report the before/after CC

```
Before: parse_token  CC=22  complexity_score=10.3
After:  parse_token  CC=11  complexity_score=7.1

✓ VERIFIED — complexity dropped by 11 points
```

> **Setup:** Claude Code loads custom commands from `.claude/commands/` at startup.
> Launch it from inside the `codespy` directory: `cd ~/codespy && claude`
> If you see `Unknown skill: refactor-loop`, you launched from the wrong directory.

---

## `codespy target` — machine-readable prioritization

```bash
codespy target ./my-project          # machine-readable JSON (default)
codespy target ./my-project --human  # structured human-readable summary
```

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

Files are ranked by a **per-file risk score**: complexity (40%), smells (35%), duplication (15%), size (10%). A file must have a hotspot (CC ≥ 10) or at least two structural smells to qualify — low-signal files are filtered out.

---

## What gets measured

| Dimension | Method | Quality score weight |
|---|---|---|
| Cyclomatic complexity | AST-precise for Python; regex for JS/TS/Go/Java/SQL/others | 40% |
| Code smells | Long functions, deep nesting, too many args, magic numbers, long files, TODOs | 35% |
| Duplication | Hash-first 6-line window matching + SequenceMatcher ≥ 85% similarity | 25% |

**Quality score** (0–100, letter grade A–F) uses the weights above.
**Per-file risk score** (used by `codespy target`) uses a separate formula: complexity 40%, smells 35%, duplication 15%, size 10%.

Hotspot threshold: CC ≥ 10 flagged, CC ≥ 15 critical.
51 file extensions supported.

---

## Usage

```bash
# Scan (HTML report auto-opens in browser on supported platforms)
codespy ./my-project

# Other report formats
codespy ./my-project --report md --report-out summary.md
codespy ./my-project --report csv

# Skip slow analyses on large repos
codespy ./my-project --no-duplication

# Exclude paths
codespy ./my-project --exclude "*/migrations/*" --exclude "*/vendor/*"

# Quiet / CI mode (no browser, no progress output)
codespy ./my-project -q --no-open
```

Reports are written to the **current directory**, not the scanned directory.

### All flags

| Flag | Default | Description |
|---|---|---|
| `PATH` | required | Directory or file to scan |
| `--report html\|md\|csv` | `html` | Report format |
| `--report-out PATH` | `report.<ext>` | Report output path |
| `--output-json PATH` | `report.json` | JSON output path |
| `--no-complexity` | off | Skip complexity analysis |
| `--no-duplication` | off | Skip duplication analysis |
| `--no-smells` | off | Skip smell detection |
| `--exclude GLOB` | — | Exclude files matching glob (repeatable) |
| `--no-open` | off | Do not auto-open HTML report |
| `-q / --quiet` | off | Suppress progress output |

Default ignored: `.git`, `__pycache__`, `.venv`, `venv`, `node_modules`, `dist`, `build`, `target`, `dbt_packages`.

---

## Requirements

Python 3.11+. No required third-party dependencies.

Optional (auto-detected at runtime):
- `click` — improved CLI experience
- `jinja2` — HTML template rendering (stdlib fallback included)

---

## Troubleshooting

**`command not found: codespy`** — Run `pip install -e .` from inside the activated venv, then verify with `codespy --version`.

**`pip install` fails with "externally-managed-environment"** — You're using a Homebrew-managed Python without a venv. Either use a venv (recommended) or add `--break-system-packages`.

**`Unknown skill: refactor-loop`** — Claude Code must be launched from inside the `codespy` directory. Exit and run `cd ~/codespy && claude`.

**`No module named pytest`** — Activate your venv first (`. .venv/bin/activate`), then run `pip install -e ".[dev]"`.

---

## Running tests

```bash
python3 -m pytest tests/ -v   # expects: 21 passed
```

---

## Project structure

```
codespy/
├── cli.py              — scan + target subcommands
├── scanner.py          — file traversal + analysis orchestration
├── languages.py        — language detection, ignore patterns
├── metrics.py          — single-pass LOC + function counting
├── models.py           — result dataclasses
├── quality.py          — 0–100 scoring model
├── analyzers/
│   ├── complexity.py   — cyclomatic complexity
│   ├── smells.py       — smell detection
│   └── duplication.py  — hash-first block matching
└── reporters/
    ├── html_reporter.py — editorial dashboard
    ├── json_reporter.py
    └── md_reporter.py
.claude/commands/
└── refactor-loop.md    — Claude Code slash command spec
```

See [DESIGN.md](DESIGN.md) for architecture decisions and trade-offs.
