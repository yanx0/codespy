"""HTML report generator — product-style code health dashboard."""

from pathlib import Path
from ..models import ScanResult, FileResult

# ---------------------------------------------------------------------------
# Risk computation helpers
# ---------------------------------------------------------------------------

def _file_risk_score(
    f: FileResult,
    dup_files: set[str],
) -> int:
    """0-100 risk score for a single file."""
    complexity_factor = 0.0
    if f.complexity:
        complexity_factor = min(f.complexity.max_complexity / 20.0, 1.0)

    smell_factor = min(len(f.smells) / 10.0, 1.0)
    dup_factor = 1.0 if f.path in dup_files else 0.0
    size_factor = min(f.code_lines / 400.0, 1.0)

    score = (
        0.40 * complexity_factor
        + 0.35 * smell_factor
        + 0.15 * dup_factor
        + 0.10 * size_factor
    ) * 100
    return round(score)


def _risk_label(score: int) -> str:
    if score >= 70:
        return "CRITICAL"
    elif score >= 45:
        return "HIGH"
    elif score >= 20:
        return "MEDIUM"
    return "LOW"


def _file_risk_reason(f: FileResult, dup_files: set[str]) -> str:
    """One-line explanation of why this file is risky."""
    reasons = []
    if f.complexity and f.complexity.hotspots:
        top = f.complexity.hotspots[0]
        reasons.append(f"`{top.name}` has complexity {top.complexity}")
    serious_smells = [s for s in f.smells if s.type not in ("todo_fixme", "magic_number")]
    if serious_smells:
        reasons.append(f"{len(serious_smells)} structural smell(s)")
    if f.path in dup_files:
        reasons.append("involved in duplicate blocks")
    if f.code_lines > 400:
        reasons.append(f"large file ({f.code_lines} lines)")
    return "; ".join(reasons) if reasons else "elevated smell density"


def _file_risk_action(f: FileResult) -> str:
    """One-line recommended action for this file."""
    if f.complexity and f.complexity.hotspots:
        top = f.complexity.hotspots[0]
        return f"Refactor `{top.name}` — break into smaller functions"
    long_fns = [s for s in f.smells if s.type == "long_function"]
    if long_fns:
        return f"Break up {len(long_fns)} long function(s) exceeding 50 lines"
    too_many = [s for s in f.smells if s.type == "too_many_args"]
    if too_many:
        return f"Reduce parameter count in {len(too_many)} function(s)"
    if f.code_lines > 400:
        return "Split this file into focused modules"
    return "Review and address smell density"


def _compute_file_risks(result: ScanResult) -> list[dict]:
    """Return top-N files ranked by risk score."""
    dup_files: set[str] = set()
    if result.duplication:
        for p in result.duplication.pairs:
            dup_files.add(p.file_a)
            dup_files.add(p.file_b)

    ranked = []
    for f in result.files:
        score = _file_risk_score(f, dup_files)
        if score == 0:
            continue
        ranked.append({
            "path": f.path,
            "risk_score": score,
            "label": _risk_label(score),
            "reason": _file_risk_reason(f, dup_files),
            "action": _file_risk_action(f),
            "code_lines": f.code_lines,
            "smells": len(f.smells),
            "max_complexity": f.complexity.max_complexity if f.complexity else 0,
        })

    ranked.sort(key=lambda x: -x["risk_score"])
    return ranked


def _actions_critical_hotspots(result: ScanResult) -> list[dict]:
    """CRITICAL: very high complexity hotspots."""
    actions = []
    critical_hotspots = [
        (f.path, h)
        for f in result.files if f.complexity
        for h in f.complexity.hotspots if h.complexity >= 15
    ]
    if critical_hotspots:
        worst = sorted(critical_hotspots, key=lambda x: -x[1].complexity)[:3]
        for path, h in worst:
            actions.append({
                "priority": "CRITICAL",
                "action": f"Refactor `{h.name}` in `{path}`",
                "detail": f"Cyclomatic complexity {h.complexity} — split into smaller, independently testable functions",
            })
    return actions


def _actions_duplication_high(result: ScanResult) -> list[dict]:
    """HIGH: duplication — differentiate SQL header patterns from general code duplication."""
    if not result.duplication or result.duplication.duplication_percent <= 10:
        return []
    sql_pairs = sum(
        1 for p in result.duplication.pairs
        if p.file_a.endswith(".sql") or p.file_b.endswith(".sql")
    )
    is_sql_heavy = sql_pairs > result.duplication.duplicate_pairs * 0.25
    if is_sql_heavy:
        return [{
            "priority": "HIGH",
            "action": "Extract shared SQL headers into a dbt base macro or config block",
            "detail": f"{result.duplication.duplication_percent:.0f}% of lines appear in shared patterns "
                      f"({result.duplication.duplicate_pairs} block pairs) — most are repeated model "
                      "config headers that belong in a single macro",
        }]
    return [{
        "priority": "HIGH",
        "action": f"Consolidate {result.duplication.duplicate_pairs} duplicated code blocks",
        "detail": f"{result.duplication.duplication_percent:.0f}% of lines appear in shared patterns "
                  "— extract into reusable functions or shared modules",
    }]


def _actions_high_hotspots(result: ScanResult) -> list[dict]:
    """HIGH: hotspots below CRITICAL threshold."""
    high_hotspots = [
        (f.path, h)
        for f in result.files if f.complexity
        for h in f.complexity.hotspots if 10 <= h.complexity < 15
    ]
    if not high_hotspots:
        return []
    worst_path, worst_h = sorted(high_hotspots, key=lambda x: -x[1].complexity)[0]
    return [{
        "priority": "HIGH",
        "action": f"Simplify {len(high_hotspots)} high-complexity "
                  f"function{'s' if len(high_hotspots) > 1 else ''} — start with `{worst_h.name}`",
        "detail": f"`{worst_h.name}` in `{worst_path}` has complexity {worst_h.complexity} "
                  "— extract conditional branches into named helper functions",
    }]


def _actions_long_functions(result: ScanResult) -> list[dict]:
    """HIGH/MEDIUM: long functions."""
    long_fns = [s for f in result.files for s in f.smells if s.type == "long_function"]
    if len(long_fns) >= 3:
        worst_long = sorted(long_fns, key=lambda s: -int(s.detail.split()[0]) if s.detail else 0)
        return [{
            "priority": "HIGH",
            "action": f"Break up {len(long_fns)} long functions",
            "detail": f"Longest is `{worst_long[0].name}` ({worst_long[0].detail}) — "
                      "extract logical sub-steps into named functions to improve testability",
        }]
    actions = []
    for s in long_fns:
        actions.append({
            "priority": "MEDIUM",
            "action": f"Shorten `{s.name}` ({s.detail})",
            "detail": "Functions over 50 lines typically handle too many concerns — split at logical boundaries",
        })
    return actions


def _actions_magic_numbers(result: ScanResult) -> list[dict]:
    """MEDIUM: magic numbers — only flag if count is significant."""
    magic_count = sum(1 for f in result.files for s in f.smells if s.type == "magic_number")
    if magic_count < 10:
        return []
    magic_by_file = sorted(
        [(f.path, sum(1 for s in f.smells if s.type == "magic_number")) for f in result.files],
        key=lambda x: -x[1]
    )
    worst_magic_file = magic_by_file[0][0].split("/")[-1] if magic_by_file else "unknown"
    return [{
        "priority": "MEDIUM",
        "action": f"Replace {magic_count} magic numbers with named constants",
        "detail": f"Most concentrated in `{worst_magic_file}` — named constants make intent explicit "
                  "and eliminate silent bugs when values change",
    }]


def _actions_deep_nesting(result: ScanResult) -> list[dict]:
    """MEDIUM: deep nesting."""
    nesting_count = sum(1 for f in result.files for s in f.smells if s.type == "deep_nesting")
    if nesting_count >= 2:
        nested_files = sorted(
            [(f.path, sum(1 for s in f.smells if s.type == "deep_nesting")) for f in result.files
             if any(s.type == "deep_nesting" for s in f.smells)],
            key=lambda x: -x[1]
        )
        worst_nested = nested_files[0][0].split("/")[-1] if nested_files else "unknown"
        return [{
            "priority": "MEDIUM",
            "action": f"Flatten deep nesting in `{worst_nested}` and {nesting_count - 1} other location{'s' if nesting_count > 2 else ''}",
            "detail": "4+ levels of indentation signals tangled control flow — use early returns and guard clauses",
        }]
    if nesting_count == 1:
        nested_file = next(
            (f.path.split("/")[-1] for f in result.files if any(s.type == "deep_nesting" for s in f.smells)),
            "unknown"
        )
        return [{
            "priority": "MEDIUM",
            "action": f"Flatten deep nesting in `{nested_file}`",
            "detail": "4+ levels of indentation signals tangled control flow — use early returns and guard clauses",
        }]
    return []


def _actions_too_many_args(result: ScanResult) -> list[dict]:
    """MEDIUM: too many args."""
    args_count = sum(1 for f in result.files for s in f.smells if s.type == "too_many_args")
    if args_count < 2:
        return []
    return [{
        "priority": "MEDIUM",
        "action": f"Reduce parameter counts in {args_count} functions",
        "detail": "Functions with 5+ parameters are error-prone to call — group related params into a config dataclass",
    }]


def _actions_moderate_duplication(result: ScanResult) -> list[dict]:
    """MEDIUM: moderate duplication."""
    if not result.duplication or not (3 <= result.duplication.duplication_percent <= 10):
        return []
    return [{
        "priority": "MEDIUM",
        "action": "Consolidate repeated code patterns before they compound",
        "detail": f"{result.duplication.duplication_percent:.0f}% of lines appear in shared patterns "
                  "— extract now while the surface area is still small",
    }]


def _actions_todos(result: ScanResult) -> list[dict]:
    """LOW: TODOs."""
    todo_count = sum(1 for f in result.files for s in f.smells if s.type == "todo_fixme")
    if todo_count <= 3:
        return []
    return [{
        "priority": "LOW",
        "action": f"Convert {todo_count} TODO/FIXME comments to tracked issues",
        "detail": "Inline markers get ignored over time — move them to your issue tracker with owners and deadlines",
    }]


def _recommended_actions(result: ScanResult) -> list[dict]:
    """Rule-based prioritized action list."""
    actions = []
    actions.extend(_actions_critical_hotspots(result))
    actions.extend(_actions_duplication_high(result))
    actions.extend(_actions_high_hotspots(result))
    actions.extend(_actions_long_functions(result))
    actions.extend(_actions_magic_numbers(result))
    actions.extend(_actions_deep_nesting(result))
    actions.extend(_actions_too_many_args(result))
    actions.extend(_actions_moderate_duplication(result))
    actions.extend(_actions_todos(result))
    return actions[:8]  # cap at 8


def _executive_summary(result: ScanResult, actions: list[dict], top_risks: list[dict]) -> str:
    """Generate a plain-English executive summary."""
    q = result.quality
    grade = q.grade if q else "?"
    score = q.score if q else 0

    # Grade maps to a sentence predicate (not a noun phrase)
    grade_verdict = {
        "A": "is in excellent health",
        "B": "is in good shape with minor issues",
        "C": "has moderate issues that should be addressed",
        "D": "requires attention before scaling",
        "F": "is in critical condition — high technical debt risk",
    }.get(grade, "has an unknown health status")

    # Find the weakest sub-dimension
    if q:
        sub = {"Complexity": q.complexity_score, "Code Smells": q.smell_score, "Duplication": q.duplication_score}
        worst_dim = min(sub, key=sub.get)
        worst_score = sub[worst_dim]
    else:
        worst_dim, worst_score = "overall quality", score

    # Build the primary driver sentence
    primary_driver = ""
    if worst_score < 50 and worst_dim == "Duplication" and result.duplication:
        d = result.duplication
        sql_pairs = sum(1 for p in d.pairs if p.file_a.endswith(".sql") or p.file_b.endswith(".sql"))
        if sql_pairs > d.duplicate_pairs * 0.4:
            primary_driver = (
                f"The score is driven primarily by <strong>widespread SQL model duplication</strong>: "
                f"{d.duplicate_pairs} block pairs share {d.duplicated_lines} lines "
                f"({d.duplication_percent:.0f}% of the codebase) — most are repeated config headers "
                f"across materialized views."
            )
        else:
            primary_driver = (
                f"The primary drag is <strong>code duplication</strong>: {d.duplicate_pairs} repeated "
                f"block pairs covering {d.duplication_percent:.0f}% of the codebase."
            )
    elif worst_score < 60:
        primary_driver = (
            f"The weakest dimension is <strong>{worst_dim}</strong> ({worst_score}/100), "
            "which is the primary driver of the low grade."
        )

    # Best next action
    high_actions = [a for a in actions if a["priority"] in ("CRITICAL", "HIGH")]
    next_step = ""
    if high_actions:
        next_step = f"Highest-impact next step: <strong>{high_actions[0]['action']}</strong>."

    parts = [
        f"This codebase scores <strong>{grade} ({score}/100)</strong> and {grade_verdict}."
    ]
    if primary_driver:
        parts.append(primary_driver)

    # Secondary concerns (smells summary)
    smell_counts = result.smells_by_type
    serious_smells = {k: v for k, v in smell_counts.items() if k not in ("todo_fixme",)}
    if serious_smells:
        _smell_labels = {
            "magic_number": ("magic number", "magic numbers"),
            "deep_nesting": ("instance of deep nesting", "instances of deep nesting"),
            "long_function": ("long function", "long functions"),
            "too_many_args": ("function with too many parameters", "functions with too many parameters"),
            "long_file": ("oversized file", "oversized files"),
        }
        top_smells = sorted(serious_smells.items(), key=lambda x: -x[1])[:2]
        smell_desc = " and ".join(
            f"{v} {_smell_labels.get(k, (k, k + 's'))[1 if v > 1 else 0]}"
            for k, v in top_smells
        )
        parts.append(f"Secondary concerns include {smell_desc}.")

    if next_step:
        parts.append(next_step)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeSpy — Code Health Report</title>
<style>
  :root {
    --bg: #fafaf8; --surface: #ffffff; --light: #f0f0ec;
    --border: #e5e5e0; --text: #1a1a1a; --muted: #6b6b6b;
    --accent: #2563eb; --accent-light: #dbeafe;
    --crit: #dc2626; --crit-bg: #fef2f2; --crit-border: #fecaca;
    --high: #ea580c; --high-bg: #fff7ed; --high-border: #fed7aa;
    --med: #d97706;  --med-bg: #fffbeb;  --med-border: #fde68a;
    --low: #2563eb;  --low-bg: #eff6ff;  --low-border: #bfdbfe;
    --green: #16a34a; --green-bg: #f0fdf4; --green-border: #bbf7d0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; }

  .page { max-width: 1100px; margin: 0 auto; padding: 3rem 2rem 6rem; }

  /* Editorial header */
  .site-header { border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; margin-bottom: 3.5rem; }
  .site-label { font-size: 0.68rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 0.5rem; }
  .site-title { font-family: Georgia, 'Times New Roman', serif; font-size: 2.2rem; font-weight: 700; line-height: 1.2; margin-bottom: 0.4rem; }
  .site-subtitle { font-size: 0.82rem; color: var(--muted); }

  /* Two-column editorial row */
  .row { display: grid; grid-template-columns: 1fr 320px; gap: 3rem; margin-bottom: 4rem; align-items: start; }
  .row.full { grid-template-columns: 1fr; }
  @media (max-width: 800px) { .row { grid-template-columns: 1fr; } }

  /* Annotation card (right column) */
  .note { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); padding: 1.4rem 1.5rem; }
  .note-label { font-size: 0.62rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 0.75rem; }
  .note-head { font-family: Georgia, serif; font-size: 1.3rem; font-weight: 700; line-height: 1.3; margin-bottom: 0.75rem; color: var(--text); }
  .note-body { font-size: 0.83rem; color: var(--muted); line-height: 1.75; }

  /* Section number label */
  .sec { font-size: 0.62rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 1.25rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }

  /* Grade + score */
  .grade-display { display: flex; align-items: baseline; gap: 0.6rem; margin-bottom: 1.75rem; }
  .grade-letter { font-family: Georgia, serif; font-size: 4.5rem; font-weight: 700; line-height: 1; }
  .grade-score { font-size: 1.4rem; font-weight: 300; color: var(--muted); }
  .grade-A { color: #16a34a; } .grade-B { color: #65a30d; }
  .grade-C { color: #d97706; } .grade-D { color: #ea580c; } .grade-F { color: #dc2626; }

  /* Score dims */
  .dim { margin-bottom: 1.1rem; }
  .dim-top { display: flex; justify-content: space-between; margin-bottom: 0.35rem; }
  .dim-label { font-size: 0.8rem; color: var(--text); }
  .dim-val { font-size: 0.8rem; font-weight: 700; }
  .dim-track { background: var(--light); height: 5px; border-radius: 2px; }
  .dim-fill { height: 5px; border-radius: 2px; }
  .dim-note { font-size: 0.73rem; color: var(--muted); margin-top: 0.25rem; }

  /* Risk cards */
  .risk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.65rem; }
  @media (max-width: 600px) { .risk-grid { grid-template-columns: 1fr; } }
  .risk-card { background: var(--surface); border: 1px solid var(--border); padding: 0.9rem 1rem; }
  .risk-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.35rem; }
  .risk-fn { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.75rem; font-weight: 600; word-break: break-all; }
  .risk-why { font-size: 0.75rem; color: var(--muted); margin-bottom: 0.35rem; }
  .risk-do { font-size: 0.75rem; color: var(--accent); }

  /* Badges */
  .badge { display: inline-block; padding: 0.12rem 0.4rem; font-size: 0.62rem; font-weight: 700; letter-spacing: 0.04em; border: 1px solid transparent; }
  .badge-CRITICAL { background: var(--crit-bg); color: var(--crit); border-color: var(--crit-border); }
  .badge-HIGH     { background: var(--high-bg); color: var(--high); border-color: var(--high-border); }
  .badge-MEDIUM   { background: var(--med-bg);  color: var(--med);  border-color: var(--med-border); }
  .badge-LOW      { background: var(--low-bg);  color: var(--low);  border-color: var(--low-border); }
  .badge-ok       { background: var(--green-bg); color: var(--green); border-color: var(--green-border); }
  .badge-lang     { background: var(--light); color: var(--muted); border-color: var(--border); }

  /* Hotspot rows */
  .hs { display: flex; align-items: center; gap: 0.65rem; padding: 0.5rem 0; border-bottom: 1px solid var(--light); }
  .hs:last-child { border-bottom: none; }
  .hs-fn { font-family: 'SF Mono', monospace; font-size: 0.75rem; min-width: 150px; }
  .hs-track { flex: 1; background: var(--light); height: 5px; border-radius: 2px; }
  .hs-fill { height: 5px; border-radius: 2px; background: var(--crit); }
  .hs-val { font-size: 0.75rem; font-weight: 700; min-width: 26px; text-align: right; }
  .hs-file { font-size: 0.7rem; color: var(--muted); min-width: 140px; }

  /* Actions */
  .act { display: flex; gap: 1rem; padding: 0.9rem 0; border-bottom: 1px solid var(--border); align-items: flex-start; }
  .act:last-child { border-bottom: none; }
  .act-n { font-size: 0.62rem; font-weight: 700; color: var(--muted); min-width: 18px; padding-top: 0.2rem; }
  .act-body { flex: 1; }
  .act-title { font-size: 0.875rem; font-weight: 600; margin-bottom: 0.2rem; }
  .act-detail { font-size: 0.78rem; color: var(--muted); line-height: 1.65; }

  /* Stats */
  .stats4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
  @media (max-width: 600px) { .stats4 { grid-template-columns: 1fr 1fr; } }
  .stat-val { font-family: Georgia, serif; font-size: 2rem; font-weight: 700; line-height: 1; margin-bottom: 0.15rem; }
  .stat-lbl { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; }

  /* Charts */
  canvas { max-width: 100%; }
  .chart-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem; }
  @media (max-width: 600px) { .chart-2 { grid-template-columns: 1fr; } }
  .chart-lbl { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.6rem; }
  .chart-h { position: relative; height: 200px; }

  /* Dup stats */
  .dup3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }

  /* Tables */
  .tbl-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
  th { text-align: left; padding: 0.5rem 0.6rem; color: var(--muted); font-weight: 600; border-bottom: 2px solid var(--border); font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.06em; cursor: pointer; user-select: none; }
  th::after { content: " ⇅"; opacity: 0.3; }
  td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--light); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--light); }
  .row-critical td:first-child { border-left: 2px solid var(--crit); }
  .row-high     td:first-child { border-left: 2px solid var(--high); }
  .row-medium   td:first-child { border-left: 2px solid var(--med); }
  .row-low      td:first-child { border-left: 2px solid var(--border); }
  code { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.82em; }

  .divider { border: none; border-top: 1px solid var(--border); margin: 1rem 0 3.5rem; }
  .footer { text-align: center; color: var(--muted); font-size: 0.72rem; font-style: italic; margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<div class="page">

<!-- HEADER -->
<header class="site-header">
  <div class="site-label">CodeSpy &nbsp;·&nbsp; Code Health Report</div>
  <h1 class="site-title">{{ scanned_path }}</h1>
  <div class="site-subtitle">
    {{ total_files }} files &nbsp;·&nbsp; {{ total_code_lines_fmt }} lines of code
    &nbsp;·&nbsp; scanned {{ scanned_at }} &nbsp;·&nbsp; {{ duration_seconds }}s
  </div>
</header>

<!-- 01 — THE SCORE -->
<div class="row">
  <div>
    <div class="sec">01 — The Score</div>
    <div class="grade-display">
      <span class="grade-letter grade-{{ grade }}">{{ grade }}</span>
      <span class="grade-score">{{ score }}/100</span>
    </div>
    {% for dim in score_dims %}
    <div class="dim">
      <div class="dim-top">
        <span class="dim-label">{{ dim.label }}</span>
        <span class="dim-val" style="color:{{ dim.color }}">{{ dim.score }}</span>
      </div>
      <div class="dim-track"><div class="dim-fill" style="width:{{ dim.score }}%;background:{{ dim.color }}"></div></div>
      <div class="dim-note">{{ dim.note }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="note">
    <div class="note-label">01 — The Score</div>
    <div class="note-head">{{ grade_headline }}</div>
    <div class="note-body">{{ executive_summary }}</div>
  </div>
</div>

<!-- 02 — RISK FILES -->
{% if top_risks %}
<div class="row">
  <div>
    <div class="sec">02 — Risk Files</div>
    <div class="risk-grid">
      {% for r in top_risks %}
      <div class="risk-card">
        <div class="risk-top">
          <div class="risk-fn">{{ r.path.split('/')|last }}</div>
          <span class="badge badge-{{ r.label }}">{{ r.label }}</span>
        </div>
        <div class="risk-why">{{ r.reason }}</div>
        <div class="risk-do">→ {{ r.action }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  <div class="note">
    <div class="note-label">02 — Risk Files</div>
    <div class="note-head">{{ top_risks|length }} file{{ 's' if top_risks|length != 1 else '' }} need{{ '' if top_risks|length != 1 else 's' }} attention.</div>
    <div class="note-body">
      Files ranked by composite risk: complexity (40%), smells (35%), duplication (15%), size (10%).
      {% if top_risks %}Highest-risk file: <strong style="color:var(--text)">{{ top_risks[0].path.split('/')|last }}</strong> — {{ top_risks[0].reason }}.{% endif %}
    </div>
  </div>
</div>
{% endif %}

<!-- 03 — WHAT TO FIX -->
{% if actions %}
<div class="row full">
  <div>
    <div class="sec">03 — What to Fix &nbsp;·&nbsp; priority order</div>
    {% for a in actions %}
    <div class="act">
      <div class="act-n">{{ loop.index }}</div>
      <div class="act-body">
        <div class="act-title">
          <span class="badge badge-{{ a.priority }}" style="margin-right:0.4rem">{{ a.priority }}</span>
          {{ a.action }}
        </div>
        <div class="act-detail">{{ a.detail }}</div>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- 04 — COMPLEXITY -->
<div class="row">
  <div>
    <div class="sec">04 — Complexity Hotspots</div>
    {% if hotspot_rows %}
      {% for h in hotspot_rows %}
      <div class="hs">
        <div class="hs-fn">{{ h.name }}</div>
        <div class="hs-track">
          <div class="hs-fill" style="width:{{ min(h.complexity * 5, 100) }}%;{% if h.complexity < 10 %}background:#a5b4fc{% elif h.complexity < 15 %}background:var(--high){% else %}background:var(--crit){% endif %}"></div>
        </div>
        <div class="hs-val" style="color:{% if h.complexity >= 15 %}var(--crit){% elif h.complexity >= 10 %}var(--high){% else %}var(--muted){% endif %}">{{ h.complexity }}</div>
        <div class="hs-file">{{ h.path.split('/')|last }}:{{ h.line }}</div>
      </div>
      {% endfor %}
    {% elif top_complexity_files %}
      <div style="color:var(--green);font-size:0.82rem;font-weight:600;margin-bottom:1rem">✓ No functions exceed CC ≥ 10</div>
      {% for f in top_complexity_files %}
      <div class="hs">
        <div class="hs-fn" style="min-width:180px">{{ f.path.split('/')|last }}</div>
        <div class="hs-track"><div class="hs-fill" style="width:{{ min(f.max_cc * 10, 100) }}%;background:#a5b4fc"></div></div>
        <div class="hs-val" style="color:#6366f1">{{ f.max_cc }}</div>
      </div>
      {% endfor %}
    {% else %}
      <div style="color:var(--muted);font-size:0.82rem">No complexity data available.</div>
    {% endif %}
  </div>
  <div class="note">
    <div class="note-label">04 — Complexity</div>
    {% if hotspot_rows %}
    <div class="note-head">{{ hotspot_rows|length }} function{{ 's' if hotspot_rows|length != 1 else '' }} above threshold.</div>
    <div class="note-body">Cyclomatic complexity (CC) counts independent paths through a function. CC ≥ 10 means hard to test. CC ≥ 15 is critical. Target: every function below 10.</div>
    {% else %}
    <div class="note-head">No hotspots.</div>
    <div class="note-body">Every function is below CC ≥ 10. Complexity score: <strong style="color:var(--text)">{{ complexity_score }}/100</strong>.</div>
    {% endif %}
  </div>
</div>

<hr class="divider">

<!-- 05 — CODEBASE OVERVIEW -->
<div class="row full">
  <div>
    <div class="sec">05 — Codebase Overview</div>

    <!-- Verdict table: why it scored this way -->
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem;margin-bottom:2rem">
      <thead>
        <tr>
          <th style="text-align:left;padding:0.4rem 0.6rem;color:var(--muted);font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;border-bottom:2px solid var(--border)">Dimension</th>
          <th style="text-align:right;padding:0.4rem 0.6rem;color:var(--muted);font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;border-bottom:2px solid var(--border)">Score</th>
          <th style="text-align:left;padding:0.4rem 0.6rem;color:var(--muted);font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;border-bottom:2px solid var(--border)">Primary driver</th>
        </tr>
      </thead>
      <tbody>
        {% for dim in score_dims %}
        <tr>
          <td style="padding:0.5rem 0.6rem;border-bottom:1px solid var(--light);font-weight:500">{{ dim.label }}</td>
          <td style="padding:0.5rem 0.6rem;border-bottom:1px solid var(--light);text-align:right;font-weight:700;color:{{ dim.color }}">{{ dim.score }}/100</td>
          <td style="padding:0.5rem 0.6rem;border-bottom:1px solid var(--light);color:var(--muted)">{{ dim.note }}</td>
        </tr>
        {% endfor %}
        <tr style="background:var(--light)">
          <td style="padding:0.5rem 0.6rem;font-weight:700">Overall</td>
          <td style="padding:0.5rem 0.6rem;text-align:right;font-weight:700;color:{% if score >= 80 %}var(--green){% elif score >= 60 %}var(--med){% else %}var(--crit){% endif %}">{{ score }}/100</td>
          <td style="padding:0.5rem 0.6rem;color:var(--muted)">{{ total_files }} files &nbsp;·&nbsp; {{ total_code_lines_fmt }} lines &nbsp;·&nbsp; {{ total_functions }} functions</td>
        </tr>
      </tbody>
    </table>

    <div class="chart-2">
      <div>
        <div class="chart-lbl">Languages</div>
        <div class="chart-h"><canvas id="langChart"></canvas></div>
      </div>
      <div>
        <div class="chart-lbl">Code Composition</div>
        <div class="chart-h"><canvas id="compChart"></canvas></div>
      </div>
    </div>
  </div>
</div>

<!-- 06 — DUPLICATION -->
{% if duplication %}
<hr class="divider">
<div class="row">
  <div>
    <div class="sec">06 — Duplication</div>
    <div class="dup3">
      <div><div class="stat-val">{{ dup_pct }}%</div><div class="stat-lbl">of Code</div></div>
      <div><div class="stat-val">{{ dup_pairs }}</div><div class="stat-lbl">Block Pairs</div></div>
      <div><div class="stat-val">{{ dup_lines }}</div><div class="stat-lbl">Shared Lines</div></div>
    </div>
    {% if dup_pair_rows %}
    <div class="tbl-wrap">
      <table>
        <tr><th>File A</th><th>Lines</th><th>File B</th><th>Lines</th><th>Match</th></tr>
        {% for row in dup_pair_rows %}
        <tr>
          <td><code>{{ row.file_a.split('/')|last }}</code></td><td style="color:var(--muted)">{{ row.lines_a }}</td>
          <td><code>{{ row.file_b.split('/')|last }}</code></td><td style="color:var(--muted)">{{ row.lines_b }}</td>
          <td><span class="badge badge-{{ 'CRITICAL' if row.sim_num >= 0.95 else ('HIGH' if row.sim_num >= 0.85 else 'MEDIUM') }}">{{ row.sim }}</span></td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}
  </div>
  <div class="note">
    <div class="note-label">06 — Duplication</div>
    <div class="note-head">{{ dup_pct }}% of lines shared.</div>
    <div class="note-body">{{ dup_pairs }} block pair{{ 's' if dup_pairs != 1 else '' }} detected across {{ dup_lines }} unique lines. Blocks are identified by hash then confirmed with SequenceMatcher similarity ≥ 85%.</div>
  </div>
</div>
{% endif %}

<!-- 07 — CODE SMELLS -->
{% if smell_summary %}
<hr class="divider">
<div class="row">
  <div>
    <div class="sec">07 — Code Smells</div>
    <div class="chart-h"><canvas id="smellChart"></canvas></div>
  </div>
  <div class="note">
    <div class="note-label">07 — Code Smells</div>
    <div class="note-head">{{ total_smells }} smell{{ 's' if total_smells != 1 else '' }} detected.</div>
    <div class="note-body">
      {% for row in smell_summary[:4] %}
      <div style="display:flex;justify-content:space-between;padding:0.3rem 0;border-bottom:1px solid var(--light)">
        <span>{{ row.type.replace('_', ' ') }}</span>
        <strong style="color:var(--text)">{{ row.count }}</strong>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}

<hr class="divider">

<!-- 08 — ALL FILES -->
<div class="row full">
  <div>
    <div class="sec">08 — All Files &nbsp;·&nbsp; click any column to sort</div>
    <div class="tbl-wrap">
      <table id="fileTable">
        <tr><th>File</th><th>Risk</th><th>Lang</th><th>Lines</th><th>Code</th><th>Fn</th><th>Max CC</th><th>Smells</th></tr>
        {% for f in file_rows %}
        <tr class="row-{{ f.risk_label|lower }}">
          <td><code>{{ f.path }}</code></td>
          <td><span class="badge badge-{{ f.risk_label }}">{{ f.risk_score }}</span></td>
          <td><span class="badge badge-lang">{{ f.language }}</span></td>
          <td>{{ f.lines }}</td>
          <td>{{ f.code_lines }}</td>
          <td>{{ f.functions }}</td>
          <td>{% if f.max_cc %}<span style="color:{% if f.max_cc >= 15 %}var(--crit){% elif f.max_cc >= 10 %}var(--high){% else %}var(--text){% endif %}">{{ f.max_cc }}</span>{% else %}—{% endif %}</td>
          <td>{% if f.smell_count %}<span class="badge badge-{{ 'HIGH' if f.smell_count >= 5 else 'MEDIUM' }}">{{ f.smell_count }}</span>{% else %}—{% endif %}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>
</div>

<footer class="footer">
  Generated by CodeSpy v0.1.0 &nbsp;·&nbsp; {{ scanned_at }} &nbsp;·&nbsp; {{ total_files }} files in {{ duration_seconds }}s
</footer>

</div>

<script>
const PAL = ['#a5b4fc','#fb923c','#86efac','#c084fc','#67e8f9','#fde68a','#f9a8d4','#6ee7b7','#94a3b8','#fca5a5'];
const LOPTS = {
  plugins: { legend: { labels: { color: '#6b6b6b', font: { size: 11 } } } },
  responsive: true, maintainAspectRatio: false
};
new Chart(document.getElementById('langChart'), {
  type: 'doughnut',
  data: { labels: {{ lang_labels }}, datasets: [{ data: {{ lang_values }}, backgroundColor: PAL, borderWidth: 2, borderColor: '#fafaf8' }] },
  options: { ...LOPTS, cutout: '52%' },
});
new Chart(document.getElementById('compChart'), {
  type: 'doughnut',
  data: { labels: ['Code', 'Comments', 'Blank'], datasets: [{ data: [{{ total_code_lines }}, {{ total_comment_lines }}, {{ total_blank_lines }}], backgroundColor: ['#a5b4fc','#86efac','#e5e5e0'], borderWidth: 2, borderColor: '#fafaf8' }] },
  options: { ...LOPTS, cutout: '52%' },
});
{% if smell_chart_labels %}
new Chart(document.getElementById('smellChart'), {
  type: 'bar',
  data: { labels: {{ smell_chart_labels }}, datasets: [{ label: 'Count', data: {{ smell_chart_values }}, backgroundColor: '#a5b4fc', borderColor: '#818cf8', borderWidth: 1 }] },
  options: { ...LOPTS, indexAxis: 'y',
    plugins: { ...LOPTS.plugins, legend: { display: false } },
    scales: {
      x: { ticks: { color: '#6b6b6b', font: { size: 11 } }, grid: { color: '#f0f0ec' } },
      y: { ticks: { color: '#1a1a1a', font: { size: 11 } }, grid: { display: false } }
    }
  },
});
{% endif %}
document.querySelectorAll('#fileTable th').forEach((th, i) => {
  th.addEventListener('click', () => {
    const tbl = document.getElementById('fileTable');
    const rows = Array.from(tbl.querySelectorAll('tr')).slice(1);
    const asc = th.dataset.asc !== 'true'; th.dataset.asc = asc;
    rows.sort((a, b) => {
      const av = a.cells[i].innerText.trim(), bv = b.cells[i].innerText.trim();
      const an = parseFloat(av), bn = parseFloat(bv);
      if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
    rows.forEach(r => tbl.appendChild(r));
  });
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Score dimension helper
# ---------------------------------------------------------------------------

def _score_color(score: int) -> str:
    if score >= 80:
        return "#22c55e"
    elif score >= 60:
        return "#eab308"
    elif score >= 40:
        return "#f97316"
    return "#ef4444"


def _score_note(label: str, score: int, result: ScanResult) -> str:
    if label == "Complexity":
        hotspots = sum(len(f.complexity.hotspots) for f in result.files if f.complexity)
        if hotspots:
            return f"{hotspots} function(s) exceed CC threshold"
        avg_cc = sum(
            f.complexity.average for f in result.files if f.complexity
        ) / max(sum(1 for f in result.files if f.complexity), 1)
        return f"Average CC {avg_cc:.1f} — {'acceptable' if score >= 70 else 'needs reduction'}"
    if label == "Smells":
        total = sum(len(f.smells) for f in result.files)
        serious = sum(1 for f in result.files for s in f.smells if s.type not in ("todo_fixme",))
        return f"{serious} structural smell(s) across {result.total_files} files"
    if label == "Duplication":
        if result.duplication:
            return f"{result.duplication.duplication_percent:.1f}% of code duplicated ({result.duplication.duplicate_pairs} pairs)"
        return "No duplication data"
    return ""


# ---------------------------------------------------------------------------
# Main generate / write functions
# ---------------------------------------------------------------------------

def generate(result: ScanResult) -> str:
    import json

    q = result.quality

    # Precompute risk data
    top_risks = [r for r in _compute_file_risks(result) if r["label"] != "LOW"][:6]
    actions = _recommended_actions(result)
    summary = _executive_summary(result, actions, top_risks)

    # Editorial headline for annotation card
    _grade_headlines = {
        "A": f"Grade {q.grade if q else '?'}. Clean codebase.",
        "B": f"Grade {q.grade if q else '?'}. Good shape with minor issues.",
        "C": f"Grade {q.grade if q else '?'}. Moderate issues need addressing.",
        "D": f"Grade {q.grade if q else '?'}. High debt — act before scaling.",
        "F": f"Grade {q.grade if q else '?'}. Critical condition.",
    }
    grade_headline = _grade_headlines.get(q.grade if q else "", f"Score {q.score if q else 0}/100")

    # Score dimensions
    score_dims = []
    if q:
        for label, score in [("Complexity", q.complexity_score), ("Smells", q.smell_score), ("Duplication", q.duplication_score)]:
            score_dims.append({
                "label": label,
                "score": score,
                "color": _score_color(score),
                "note": _score_note(label, score, result),
            })

    # Hotspots (above threshold)
    all_hotspots = sorted(
        [{"path": f.path, "name": h.name, "complexity": h.complexity, "line": h.line}
         for f in result.files if f.complexity for h in f.complexity.hotspots],
        key=lambda x: -x["complexity"],
    )[:20]

    # Top files by complexity — shown even when no hotspots exist
    top_complexity_files = sorted(
        [
            {
                "path": f.path,
                "max_cc": f.complexity.max_complexity,
                "avg_cc": f.complexity.average,
            }
            for f in result.files
            if f.complexity and f.complexity.max_complexity > 1
        ],
        key=lambda x: -x["max_cc"],
    )[:5]

    # Dup pairs
    dup_pair_rows = []
    if result.duplication:
        for p in result.duplication.pairs[:20]:
            dup_pair_rows.append({
                "file_a": p.file_a,
                "lines_a": f"{p.lines_a[0]}–{p.lines_a[1]}",
                "file_b": p.file_b,
                "lines_b": f"{p.lines_b[0]}–{p.lines_b[1]}",
                "sim": f"{p.similarity:.0%}",
                "sim_num": p.similarity,
            })

    # Smell summary
    smell_summary = [
        {"type": t, "count": c}
        for t, c in sorted(result.smells_by_type.items(), key=lambda x: -x[1])
    ]

    # File rows — enriched with risk score
    dup_files: set[str] = set()
    if result.duplication:
        for p in result.duplication.pairs:
            dup_files.add(p.file_a)
            dup_files.add(p.file_b)

    file_rows = sorted(
        [
            {
                "path": f.path,
                "language": f.language,
                "lines": f.lines,
                "code_lines": f.code_lines,
                "functions": f.functions,
                "smell_count": len(f.smells),
                "max_cc": f.complexity.max_complexity if f.complexity else 0,
                "risk_score": _file_risk_score(f, dup_files),
                "risk_label": _risk_label(_file_risk_score(f, dup_files)),
            }
            for f in result.files
        ],
        key=lambda x: -x["risk_score"],
    )

    ctx = {
        "scanned_path": result.scanned_path,
        "scanned_at": result.scanned_at[:19].replace("T", " ") + " UTC",
        "duration_seconds": result.duration_seconds,
        "grade": q.grade if q else "?",
        "score": q.score if q else 0,
        "total_files": result.total_files,
        "total_code_lines": result.total_code_lines,
        "total_code_lines_fmt": f"{result.total_code_lines:,}",
        "total_comment_lines": result.total_comment_lines,
        "total_blank_lines": result.total_blank_lines,
        "total_functions": f"{result.total_functions:,}",
        "total_smells": result.total_smells,
        "executive_summary": summary,
        "grade_headline": grade_headline,
        "top_risks": top_risks,
        "actions": actions,
        "score_dims": score_dims,
        "hotspot_rows": all_hotspots,
        "top_complexity_files": top_complexity_files,
        "complexity_score": q.complexity_score if q else 0,
        "duplication": result.duplication is not None,
        "dup_pairs": result.duplication.duplicate_pairs if result.duplication else 0,
        "dup_lines": result.duplication.duplicated_lines if result.duplication else 0,
        "dup_pct": result.duplication.duplication_percent if result.duplication else 0,
        "dup_pair_rows": dup_pair_rows,
        "smell_summary": smell_summary,
        "smell_chart_labels": json.dumps([s["type"] for s in smell_summary]),
        "smell_chart_values": json.dumps([s["count"] for s in smell_summary]),
        "file_rows": file_rows,
        "lang_labels": json.dumps(list(result.languages.keys())),
        "lang_values": json.dumps([v["code_lines"] for v in result.languages.values()]),
    }

    try:
        from jinja2 import Environment
        env = Environment(autoescape=False)
        env.filters["tojson"] = json.dumps
        env.globals["min"] = min
        env.globals["max"] = max

        tmpl = env.from_string(_TEMPLATE)
        return tmpl.render(**ctx)
    except ImportError:
        # Basic fallback — replace simple {{ var }} only
        import re
        result_html = _TEMPLATE
        for key, val in ctx.items():
            if isinstance(val, (str, int, float, bool)):
                result_html = result_html.replace("{{ " + key + " }}", str(val))
        return result_html


def write(result: ScanResult, output_path: str) -> None:
    Path(output_path).write_text(generate(result), encoding="utf-8")
