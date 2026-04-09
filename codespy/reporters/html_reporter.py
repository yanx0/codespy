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


def _recommended_actions(result: ScanResult) -> list[dict]:
    """Rule-based prioritized action list."""
    actions = []

    # CRITICAL: very high complexity hotspots
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
                "detail": f"Cyclomatic complexity {h.complexity} — extremely hard to test and maintain",
            })

    # HIGH: duplication
    if result.duplication and result.duplication.duplication_percent > 10:
        actions.append({
            "priority": "HIGH",
            "action": f"Eliminate duplicated code blocks",
            "detail": f"{result.duplication.duplicate_pairs} pairs, "
                      f"{result.duplication.duplication_percent:.1f}% of code is duplicated — extract shared logic",
        })

    # HIGH: hotspots below CRITICAL threshold
    high_hotspots = [
        (f.path, h)
        for f in result.files if f.complexity
        for h in f.complexity.hotspots if 10 <= h.complexity < 15
    ]
    if high_hotspots:
        actions.append({
            "priority": "HIGH",
            "action": f"Simplify {len(high_hotspots)} high-complexity function(s)",
            "detail": f"Functions with complexity 10–14 are hard to reason about — "
                      f"break them into smaller, testable units",
        })

    # HIGH: long functions
    long_fn_count = sum(
        1 for f in result.files for s in f.smells if s.type == "long_function"
    )
    if long_fn_count >= 3:
        actions.append({
            "priority": "HIGH",
            "action": f"Break up {long_fn_count} long functions (>50 lines)",
            "detail": "Long functions mix concerns and are hard to test — extract logical sub-steps",
        })

    # MEDIUM: deep nesting
    nesting_count = sum(
        1 for f in result.files for s in f.smells if s.type == "deep_nesting"
    )
    if nesting_count >= 2:
        actions.append({
            "priority": "MEDIUM",
            "action": f"Flatten deep nesting in {nesting_count} location(s)",
            "detail": "Deeply nested code (4+ levels) is a readability and bug risk — use early returns or extract guards",
        })

    # MEDIUM: too many args
    args_count = sum(
        1 for f in result.files for s in f.smells if s.type == "too_many_args"
    )
    if args_count >= 2:
        actions.append({
            "priority": "MEDIUM",
            "action": f"Reduce parameter lists in {args_count} function(s)",
            "detail": "Functions with 5+ parameters are hard to call correctly — group into config objects",
        })

    # MEDIUM: duplication under threshold
    if result.duplication and 3 <= result.duplication.duplication_percent <= 10:
        actions.append({
            "priority": "MEDIUM",
            "action": "Review and consolidate duplicate code patterns",
            "detail": f"{result.duplication.duplication_percent:.1f}% duplication detected — "
                      "consider shared utilities before it grows",
        })

    # LOW: TODOs
    todo_count = sum(
        1 for f in result.files for s in f.smells if s.type == "todo_fixme"
    )
    if todo_count > 3:
        actions.append({
            "priority": "LOW",
            "action": f"Resolve or track {todo_count} TODO/FIXME markers",
            "detail": "Convert to tracked issues or fix inline — stale TODOs erode code trust",
        })

    return actions[:8]  # cap at 8


def _executive_summary(result: ScanResult, actions: list[dict], top_risks: list[dict]) -> str:
    """Generate a plain-English executive summary."""
    q = result.quality
    grade = q.grade if q else "?"
    score = q.score if q else 0

    grade_desc = {
        "A": "excellent shape", "B": "good shape",
        "C": "moderate health", "D": "needs attention", "F": "critical condition",
    }.get(grade, "unknown state")

    # Find the weakest sub-dimension
    if q:
        sub = {"Complexity": q.complexity_score, "Code Smells": q.smell_score, "Duplication": q.duplication_score}
        worst_dim = min(sub, key=sub.get)
        worst_score = sub[worst_dim]
    else:
        worst_dim, worst_score = "overall quality", score

    # Count critical/high actions
    critical_count = sum(1 for a in actions if a["priority"] == "CRITICAL")
    high_count = sum(1 for a in actions if a["priority"] == "HIGH")

    parts = [f"This codebase scores <strong>{grade} ({score}/100)</strong> — it is in {grade_desc}."]

    if worst_score < 70:
        parts.append(
            f"The weakest dimension is <strong>{worst_dim} ({worst_score}/100)</strong>, "
            "which is pulling the overall grade down."
        )

    if top_risks:
        risky_file = top_risks[0]["path"].split("/")[-1]
        parts.append(
            f"Risk is most concentrated in <strong>{len(top_risks)} files</strong>; "
            f"`{risky_file}` is the highest-priority target."
        )

    if critical_count:
        parts.append(
            f"There {'is' if critical_count == 1 else 'are'} <strong>{critical_count} critical issue(s)</strong> "
            "that should be addressed before the next release."
        )
    elif high_count:
        parts.append(
            f"There {'is' if high_count == 1 else 'are'} <strong>{high_count} high-priority item(s)</strong> "
            "worth addressing in the next sprint."
        )
    else:
        parts.append("No critical blockers found — focus on the medium-priority improvements below.")

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
    --bg: #0b0d14; --surface: #141720; --surface2: #1c1f2e;
    --border: #252840; --text: #e2e8f0; --muted: #7a859a;
    --accent: #6366f1; --accent2: #818cf8;
    --crit: #ef4444; --crit-bg: rgba(239,68,68,0.10);
    --high: #f97316; --high-bg: rgba(249,115,22,0.10);
    --med: #eab308;  --med-bg:  rgba(234,179,8,0.10);
    --low: #3b82f6;  --low-bg:  rgba(59,130,246,0.10);
    --green: #22c55e; --green-bg: rgba(34,197,94,0.10);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6; }

  /* Layout */
  .page { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
  @media (max-width: 768px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }

  /* Typography */
  h1 { font-size: 1.5rem; font-weight: 700; }
  h2 { font-size: 0.7rem; font-weight: 600; color: var(--muted); text-transform: uppercase;
       letter-spacing: 0.1em; margin-bottom: 1rem; }
  h3 { font-size: 1rem; font-weight: 600; }
  code { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.85em;
         background: var(--surface2); padding: 0.1em 0.35em; border-radius: 3px; }
  .muted { color: var(--muted); font-size: 0.85rem; }

  /* Cards & Surfaces */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem 1.5rem; }
  .card-accent { border-left: 3px solid var(--accent); }

  /* Section spacing */
  .section { margin-bottom: 2.5rem; }

  /* Hero */
  .hero { background: linear-gradient(135deg, #141720 0%, #0f1320 100%);
          border: 1px solid var(--border); border-radius: 12px;
          padding: 2rem 2.5rem; margin-bottom: 2rem;
          display: flex; align-items: center; gap: 2.5rem; flex-wrap: wrap; }
  .hero-grade { font-size: 5rem; font-weight: 800; line-height: 1;
                text-shadow: 0 0 40px currentColor; min-width: 100px; text-align: center; }
  .hero-body { flex: 1; min-width: 280px; }
  .hero-title { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.25rem; }
  .hero-meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }
  .hero-score-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
  .big-score { font-size: 2.5rem; font-weight: 700; }
  .score-bar-wrap { flex: 1; min-width: 180px; }
  .score-bar-track { background: var(--border); border-radius: 9999px; height: 10px; }
  .score-bar-fill { height: 10px; border-radius: 9999px; background: var(--accent); }

  /* Grade colors */
  .grade-A { color: #22c55e; } .grade-B { color: #86efac; }
  .grade-C { color: #eab308; } .grade-D { color: #f97316; } .grade-F { color: #ef4444; }

  /* Executive summary */
  .summary-box { background: var(--surface2); border: 1px solid var(--border);
                 border-left: 4px solid var(--accent); border-radius: 8px;
                 padding: 1.25rem 1.5rem; font-size: 0.95rem; line-height: 1.7;
                 margin-bottom: 2rem; }

  /* Priority / Severity badges */
  .badge { display: inline-block; padding: 0.2rem 0.55rem; border-radius: 5px;
           font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; }
  .badge-CRITICAL { background: var(--crit-bg); color: var(--crit); }
  .badge-HIGH     { background: var(--high-bg); color: var(--high); }
  .badge-MEDIUM   { background: var(--med-bg);  color: var(--med);  }
  .badge-LOW      { background: var(--low-bg);  color: var(--low);  }
  .badge-ok       { background: var(--green-bg); color: var(--green); }

  /* Risk cards */
  .risk-card { background: var(--surface); border: 1px solid var(--border);
               border-radius: 10px; padding: 1.1rem 1.25rem; }
  .risk-card-header { display: flex; align-items: center; justify-content: space-between;
                      margin-bottom: 0.5rem; }
  .risk-filename { font-family: 'SF Mono', monospace; font-size: 0.82rem;
                   color: var(--accent2); font-weight: 600; }
  .risk-reason { font-size: 0.85rem; color: var(--muted); margin-bottom: 0.5rem; }
  .risk-action { font-size: 0.85rem; padding: 0.4rem 0.75rem;
                 background: var(--surface2); border-radius: 5px;
                 border-left: 2px solid var(--accent); }

  /* Penalty breakdown */
  .penalty-row { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.85rem; }
  .penalty-label { font-size: 0.85rem; min-width: 130px; color: var(--text); }
  .penalty-bar-track { flex: 1; background: var(--border); border-radius: 9999px; height: 8px; }
  .penalty-bar-fill { height: 8px; border-radius: 9999px; }
  .penalty-score { font-size: 0.85rem; font-weight: 700; min-width: 34px; text-align: right; }
  .penalty-note { font-size: 0.78rem; color: var(--muted); min-width: 200px; }

  /* Action list */
  .action-item { display: flex; gap: 1rem; padding: 0.9rem 1.1rem;
                 background: var(--surface); border: 1px solid var(--border);
                 border-radius: 8px; margin-bottom: 0.6rem; align-items: flex-start; }
  .action-num { font-size: 1.1rem; font-weight: 800; color: var(--muted);
                min-width: 24px; padding-top: 0.1rem; }
  .action-body { flex: 1; }
  .action-title { font-size: 0.92rem; font-weight: 600; margin-bottom: 0.2rem; }
  .action-detail { font-size: 0.82rem; color: var(--muted); }

  /* Stat cards */
  .stat-card { background: var(--surface); border: 1px solid var(--border);
               border-radius: 10px; padding: 1.1rem 1.25rem; text-align: center; }
  .stat-value { font-size: 1.9rem; font-weight: 700; line-height: 1.2; }
  .stat-label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase;
                letter-spacing: 0.08em; margin-top: 0.2rem; }

  /* Tables */
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; padding: 0.6rem 0.75rem; color: var(--muted); font-weight: 600;
       border-bottom: 1px solid var(--border); font-size: 0.72rem; text-transform: uppercase;
       letter-spacing: 0.06em; cursor: pointer; user-select: none; }
  th:hover { color: var(--text); }
  th::after { content: " ⇅"; opacity: 0.3; }
  td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.025); }
  .row-critical td:first-child { border-left: 3px solid var(--crit); }
  .row-high     td:first-child { border-left: 3px solid var(--high); }
  .row-medium   td:first-child { border-left: 3px solid var(--med); }
  .row-low      td:first-child { border-left: 3px solid var(--border); }

  /* Section header */
  .section-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; }
  .section-icon { font-size: 1.1rem; }
  .section-title { font-size: 1rem; font-weight: 700; }
  .section-badge { font-size: 0.72rem; color: var(--muted); background: var(--surface2);
                   border: 1px solid var(--border); border-radius: 5px;
                   padding: 0.15rem 0.5rem; }

  /* Hotspot bar */
  .hotspot-bar { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }
  .hotspot-fn { font-family: monospace; font-size: 0.82rem; min-width: 160px; color: var(--accent2); }
  .hotspot-track { flex: 1; background: var(--border); border-radius: 9999px; height: 7px; }
  .hotspot-fill { height: 7px; border-radius: 9999px; background: var(--crit); }
  .hotspot-val { font-size: 0.82rem; font-weight: 700; min-width: 30px; text-align: right; }
  .hotspot-file { font-size: 0.75rem; color: var(--muted); min-width: 180px; }

  /* Charts */
  canvas { max-width: 100%; }
  .chart-container { position: relative; height: 220px; }

  /* Divider */
  .divider { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<div class="page">

<!-- ═══════════════════════════════════════════════════════════ HERO -->
<div class="hero">
  <div class="hero-grade grade-{{ grade }}">{{ grade }}</div>
  <div class="hero-body">
    <div class="hero-title">Code Health Report</div>
    <div class="hero-meta">
      <code>{{ scanned_path }}</code> &nbsp;·&nbsp; {{ total_files }} files &nbsp;·&nbsp;
      {{ total_code_lines_fmt }} lines of code &nbsp;·&nbsp; {{ scanned_at }} &nbsp;·&nbsp; {{ duration_seconds }}s
    </div>
    <div class="hero-score-row">
      <div class="big-score grade-{{ grade }}">{{ score }}<span style="font-size:1.1rem;color:var(--muted);font-weight:400">/100</span></div>
      <div class="score-bar-wrap">
        <div class="score-bar-track">
          <div class="score-bar-fill" style="width:{{ score }}%"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ EXECUTIVE SUMMARY -->
<div class="summary-box">{{ executive_summary }}</div>

<!-- ═══════════════════════════════════════════════════════ TOP RISKS -->
{% if top_risks %}
<div class="section">
  <div class="section-header">
    <span class="section-icon">⚠</span>
    <span class="section-title">Top Risk Files</span>
    <span class="section-badge">{{ top_risks|length }} files flagged</span>
  </div>
  <div class="grid-2">
    {% for r in top_risks %}
    <div class="risk-card">
      <div class="risk-card-header">
        <span class="risk-filename">{{ r.path }}</span>
        <span class="badge badge-{{ r.label }}">{{ r.label }}</span>
      </div>
      <div class="risk-reason">{{ r.reason }}</div>
      <div class="risk-action">→ {{ r.action }}</div>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- ══════════════════════════════════════════════ SCORE BREAKDOWN -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">◎</span>
    <span class="section-title">Score Breakdown</span>
  </div>
  <div class="card">
    {% for dim in score_dims %}
    <div class="penalty-row">
      <div class="penalty-label">{{ dim.label }}</div>
      <div class="penalty-bar-track">
        <div class="penalty-bar-fill" style="width:{{ dim.score }}%;background:{{ dim.color }}"></div>
      </div>
      <div class="penalty-score" style="color:{{ dim.color }}">{{ dim.score }}</div>
      <div class="penalty-note">{{ dim.note }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<!-- ══════════════════════════════════════════ RECOMMENDED ACTIONS -->
{% if actions %}
<div class="section">
  <div class="section-header">
    <span class="section-icon">✦</span>
    <span class="section-title">Recommended Actions</span>
    <span class="section-badge">priority order</span>
  </div>
  {% for a in actions %}
  <div class="action-item">
    <div class="action-num">{{ loop.index }}</div>
    <div class="action-body">
      <div class="action-title">
        <span class="badge badge-{{ a.priority }}" style="margin-right:0.5rem">{{ a.priority }}</span>
        {{ a.action }}
      </div>
      <div class="action-detail">{{ a.detail }}</div>
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

<hr class="divider">

<!-- ═══════════════════════════════════════════════════ SUMMARY STATS -->
<div class="section">
  <h2>Codebase Overview</h2>
  <div class="grid-4" style="margin-bottom:1.5rem">
    <div class="stat-card"><div class="stat-value">{{ total_files }}</div><div class="stat-label">Files</div></div>
    <div class="stat-card"><div class="stat-value">{{ total_code_lines_fmt }}</div><div class="stat-label">Code Lines</div></div>
    <div class="stat-card"><div class="stat-value">{{ total_functions }}</div><div class="stat-label">Functions</div></div>
    <div class="stat-card"><div class="stat-value">{{ total_smells }}</div><div class="stat-label">Smells</div></div>
  </div>
  <div class="grid-2">
    <div>
      <h2>Languages</h2>
      <div class="chart-container"><canvas id="langChart"></canvas></div>
    </div>
    <div>
      <h2>Code Composition</h2>
      <div class="chart-container"><canvas id="compChart"></canvas></div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════ COMPLEXITY HOTSPOTS -->
{% if hotspot_rows %}
<div class="section">
  <div class="section-header">
    <span class="section-icon">◈</span>
    <span class="section-title">Complexity Hotspots</span>
    <span class="section-badge">{{ hotspot_rows|length }} functions above threshold (CC ≥ 10)</span>
  </div>
  <div class="card">
    {% for h in hotspot_rows %}
    <div class="hotspot-bar">
      <div class="hotspot-fn">{{ h.name }}</div>
      <div class="hotspot-track"><div class="hotspot-fill" style="width:{{ min(h.complexity * 5, 100) }}%"></div></div>
      <div class="hotspot-val">{{ h.complexity }}</div>
      <div class="hotspot-file muted">{{ h.path }}:{{ h.line }}</div>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- ════════════════════════════════════════════════════ DUPLICATION -->
{% if duplication %}
<div class="section">
  <div class="section-header">
    <span class="section-icon">⧉</span>
    <span class="section-title">Code Duplication</span>
    <span class="section-badge">{{ dup_pct }}% of code duplicated</span>
  </div>
  <div class="grid-3" style="margin-bottom:1.25rem">
    <div class="stat-card"><div class="stat-value">{{ dup_pairs }}</div><div class="stat-label">Duplicate Pairs</div></div>
    <div class="stat-card"><div class="stat-value">{{ dup_lines }}</div><div class="stat-label">Duplicated Lines</div></div>
    <div class="stat-card"><div class="stat-value">{{ dup_pct }}%</div><div class="stat-label">Duplication Rate</div></div>
  </div>
  {% if dup_pair_rows %}
  <div class="card table-wrap">
    <table>
      <tr><th>File A</th><th>Lines</th><th>File B</th><th>Lines</th><th>Similarity</th></tr>
      {% for row in dup_pair_rows %}
      <tr>
        <td><code>{{ row.file_a }}</code></td><td>{{ row.lines_a }}</td>
        <td><code>{{ row.file_b }}</code></td><td>{{ row.lines_b }}</td>
        <td><span class="badge badge-{{ 'CRITICAL' if row.sim_num >= 0.95 else ('HIGH' if row.sim_num >= 0.85 else 'MEDIUM') }}">{{ row.sim }}</span></td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}
</div>
{% endif %}

<!-- ═════════════════════════════════════════════════ CODE SMELLS -->
{% if smell_summary %}
<div class="section">
  <div class="section-header">
    <span class="section-icon">◉</span>
    <span class="section-title">Code Smells</span>
    <span class="section-badge">{{ total_smells }} total across {{ total_files }} files</span>
  </div>
  <div class="grid-2">
    <div class="card">
      <h2 style="margin-bottom:0.75rem">By Type</h2>
      {% for row in smell_summary %}
      <div class="hotspot-bar">
        <div class="hotspot-fn" style="min-width:180px">{{ row.type }}</div>
        <div class="hotspot-track"><div class="hotspot-fill" style="width:{{ min(row.count * 6, 100) }}%;background:var(--med)"></div></div>
        <div class="hotspot-val">{{ row.count }}</div>
      </div>
      {% endfor %}
    </div>
    <div class="chart-container" style="max-height:220px">
      <canvas id="smellChart"></canvas>
    </div>
  </div>
</div>
{% endif %}

<!-- ═══════════════════════════════════════════════════ FILE TABLE -->
<div class="section">
  <div class="section-header">
    <span class="section-icon">▤</span>
    <span class="section-title">All Files</span>
    <span class="section-badge">sorted by risk</span>
  </div>
  <div class="card table-wrap">
    <table id="fileTable">
      <tr>
        <th>File</th><th>Risk</th><th>Lang</th><th>Lines</th>
        <th>Code</th><th>Fn</th><th>Max CC</th><th>Smells</th>
      </tr>
      {% for f in file_rows %}
      <tr class="row-{{ f.risk_label|lower }}">
        <td><code>{{ f.path }}</code></td>
        <td>
          <span class="badge badge-{{ f.risk_label }}">{{ f.risk_score }}</span>
        </td>
        <td><span class="badge" style="background:var(--surface2);color:var(--muted)">{{ f.language }}</span></td>
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

<div style="text-align:center;color:var(--muted);font-size:0.8rem;margin-top:3rem">
  Generated by <strong>CodeSpy</strong> v0.1.0 &nbsp;·&nbsp; {{ scanned_at }}
</div>

</div><!-- /page -->

<script>
const CHART_COLORS = ['#6366f1','#22c55e','#eab308','#ef4444','#3b82f6','#f97316','#a855f7','#14b8a6','#f43f5e','#8b5cf6'];
const CHART_DEFAULTS = { plugins: { legend: { labels: { color: '#e2e8f0', font: { size: 12 } } } }, responsive: true, maintainAspectRatio: false };

new Chart(document.getElementById('langChart'), {
  type: 'doughnut',
  data: { labels: {{ lang_labels }}, datasets: [{ data: {{ lang_values }}, backgroundColor: CHART_COLORS }] },
  options: CHART_DEFAULTS,
});
new Chart(document.getElementById('compChart'), {
  type: 'doughnut',
  data: { labels: ['Code', 'Comments', 'Blank'], datasets: [{ data: [{{ total_code_lines }}, {{ total_comment_lines }}, {{ total_blank_lines }}], backgroundColor: ['#6366f1','#22c55e','#252840'] }] },
  options: CHART_DEFAULTS,
});
{% if smell_chart_labels %}
new Chart(document.getElementById('smellChart'), {
  type: 'bar',
  data: { labels: {{ smell_chart_labels }}, datasets: [{ label: 'Count', data: {{ smell_chart_values }}, backgroundColor: '#eab308aa', borderColor: '#eab308', borderWidth: 1 }] },
  options: { ...CHART_DEFAULTS, indexAxis: 'y', plugins: { ...CHART_DEFAULTS.plugins, legend: { display: false } }, scales: { x: { ticks: { color: '#7a859a' }, grid: { color: '#252840' } }, y: { ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { display: false } } } },
});
{% endif %}

// Simple client-side table sort
document.querySelectorAll('#fileTable th').forEach((th, i) => {
  th.addEventListener('click', () => {
    const table = document.getElementById('fileTable');
    const rows = Array.from(table.querySelectorAll('tr')).slice(1);
    const asc = th.dataset.asc !== 'true';
    th.dataset.asc = asc;
    rows.sort((a, b) => {
      const av = a.cells[i].innerText.trim();
      const bv = b.cells[i].innerText.trim();
      const an = parseFloat(av), bn = parseFloat(bv);
      if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
    rows.forEach(r => table.appendChild(r));
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
    top_risks = _compute_file_risks(result)[:6]
    actions = _recommended_actions(result)
    summary = _executive_summary(result, actions, top_risks)

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

    # Hotspots
    all_hotspots = sorted(
        [{"path": f.path, "name": h.name, "complexity": h.complexity, "line": h.line}
         for f in result.files if f.complexity for h in f.complexity.hotspots],
        key=lambda x: -x["complexity"],
    )[:20]

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
        "top_risks": top_risks,
        "actions": actions,
        "score_dims": score_dims,
        "hotspot_rows": all_hotspots,
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
