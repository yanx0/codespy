"""HTML report generator — uses jinja2 if available, otherwise falls back to f-strings."""

from pathlib import Path
from ..models import ScanResult

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeSpy Report — {{ scanned_path }}</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --border: #2d3142;
    --text: #e2e8f0; --muted: #8892a4; --accent: #6366f1;
    --green: #22c55e; --yellow: #eab308; --orange: #f97316;
    --red: #ef4444; --blue: #3b82f6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1, h2, h3 { font-weight: 600; }
  h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
  h2 { font-size: 1.2rem; color: var(--accent); margin: 2rem 0 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }
  .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem 1.5rem; min-width: 140px; flex: 1; }
  .card .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 2rem; font-weight: 700; margin-top: 0.25rem; }
  .grade-A { color: var(--green); }
  .grade-B { color: #86efac; }
  .grade-C { color: var(--yellow); }
  .grade-D { color: var(--orange); }
  .grade-F { color: var(--red); }
  .progress-bar { background: var(--border); border-radius: 9999px; height: 8px; margin-top: 0.5rem; }
  .progress-fill { height: 8px; border-radius: 9999px; background: var(--accent); transition: width 0.5s; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; padding: 0.5rem 0.75rem; color: var(--muted); border-bottom: 1px solid var(--border); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; }
  td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
  tr:hover td { background: var(--surface); }
  .tag { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.75rem; background: var(--border); }
  .tag-red { background: rgba(239,68,68,0.15); color: var(--red); }
  .tag-yellow { background: rgba(234,179,8,0.15); color: var(--yellow); }
  .tag-blue { background: rgba(59,130,246,0.15); color: var(--blue); }
  .section { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 1.5rem; }
  .section-header { padding: 0.75rem 1rem; background: rgba(255,255,255,0.03); border-bottom: 1px solid var(--border); font-size: 0.85rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .smell-pill { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.7rem; margin: 0.1rem; background: rgba(239,68,68,0.15); color: var(--red); }
  canvas { max-width: 100%; }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<h1>CodeSpy Report</h1>
<p class="meta">Scanned: <code>{{ scanned_path }}</code> &nbsp;|&nbsp; {{ scanned_at }} &nbsp;|&nbsp; {{ duration_seconds }}s</p>

<h2>Quality Score</h2>
<div class="cards">
  <div class="card">
    <div class="label">Overall Grade</div>
    <div class="value grade-{{ grade }}">{{ grade }}</div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ score }}%"></div></div>
  </div>
  <div class="card">
    <div class="label">Score</div>
    <div class="value">{{ score }}<span style="font-size:1rem;color:var(--muted)">/100</span></div>
  </div>
  <div class="card">
    <div class="label">Complexity</div>
    <div class="value">{{ complexity_score }}</div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ complexity_score }}%;background:var(--blue)"></div></div>
  </div>
  <div class="card">
    <div class="label">Smells</div>
    <div class="value">{{ smell_score }}</div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ smell_score }}%;background:var(--yellow)"></div></div>
  </div>
  <div class="card">
    <div class="label">Duplication</div>
    <div class="value">{{ dup_score }}</div>
    <div class="progress-bar"><div class="progress-fill" style="width:{{ dup_score }}%;background:var(--green)"></div></div>
  </div>
</div>

<h2>Summary</h2>
<div class="cards">
  <div class="card"><div class="label">Files</div><div class="value">{{ total_files }}</div></div>
  <div class="card"><div class="label">Total Lines</div><div class="value">{{ total_lines }}</div></div>
  <div class="card"><div class="label">Code Lines</div><div class="value">{{ total_code_lines }}</div></div>
  <div class="card"><div class="label">Functions</div><div class="value">{{ total_functions }}</div></div>
  <div class="card"><div class="label">Classes</div><div class="value">{{ total_classes }}</div></div>
  <div class="card"><div class="label">Smells</div><div class="value">{{ total_smells }}</div></div>
</div>

<div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1.5rem">
  <div style="flex:1;min-width:280px">
    <h2>Languages</h2>
    <canvas id="langChart" height="220"></canvas>
  </div>
  <div style="flex:1;min-width:280px">
    <h2>Code Composition</h2>
    <canvas id="compChart" height="220"></canvas>
  </div>
</div>

{% if duplication %}
<h2>Duplication</h2>
<div class="cards">
  <div class="card"><div class="label">Duplicate Pairs</div><div class="value">{{ dup_pairs }}</div></div>
  <div class="card"><div class="label">Duplicated Lines</div><div class="value">{{ dup_lines }}</div></div>
  <div class="card"><div class="label">Duplication %</div><div class="value">{{ dup_pct }}%</div></div>
</div>
{% if dup_pair_rows %}
<div class="section">
  <div class="section-header">Duplicate Pairs</div>
  <table>
    <tr><th>File A</th><th>Lines</th><th>File B</th><th>Lines</th><th>Similarity</th></tr>
    {% for row in dup_pair_rows %}
    <tr><td><code>{{ row.file_a }}</code></td><td>{{ row.lines_a }}</td><td><code>{{ row.file_b }}</code></td><td>{{ row.lines_b }}</td><td>{{ row.sim }}</td></tr>
    {% endfor %}
  </table>
</div>
{% endif %}
{% endif %}

{% if hotspot_rows %}
<h2>Complexity Hotspots</h2>
<div class="section">
  <table>
    <tr><th>File</th><th>Function</th><th>Complexity</th><th>Line</th></tr>
    {% for row in hotspot_rows %}
    <tr>
      <td><code>{{ row.path }}</code></td>
      <td><code>{{ row.name }}</code></td>
      <td><span class="tag tag-red">{{ row.complexity }}</span></td>
      <td>{{ row.line }}</td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}

{% if smell_summary %}
<h2>Code Smells ({{ total_smells }} total)</h2>
<div class="section">
  <table>
    <tr><th>Type</th><th>Count</th><th>Description</th></tr>
    {% for row in smell_summary %}
    <tr><td><span class="tag tag-yellow">{{ row.type }}</span></td><td>{{ row.count }}</td><td>{{ row.desc }}</td></tr>
    {% endfor %}
  </table>
</div>
{% endif %}

<h2>Files ({{ total_files }})</h2>
<div class="section">
  <table>
    <tr><th>File</th><th>Lang</th><th>Lines</th><th>Code</th><th>Comments</th><th>Fn</th><th>Cls</th><th>Smells</th></tr>
    {% for f in file_rows %}
    <tr>
      <td><code>{{ f.path }}</code></td>
      <td><span class="tag">{{ f.language }}</span></td>
      <td>{{ f.lines }}</td>
      <td>{{ f.code_lines }}</td>
      <td>{{ f.comment_lines }}</td>
      <td>{{ f.functions }}</td>
      <td>{{ f.classes }}</td>
      <td>{% if f.smell_count %}<span class="tag tag-red">{{ f.smell_count }}</span>{% else %}—{% endif %}</td>
    </tr>
    {% endfor %}
  </table>
</div>

<script>
const chartDefaults = {
  plugins: { legend: { labels: { color: '#e2e8f0', font: { size: 12 } } } }
};
new Chart(document.getElementById('langChart'), {
  type: 'doughnut',
  data: {
    labels: {{ lang_labels | tojson }},
    datasets: [{ data: {{ lang_values | tojson }}, backgroundColor: ['#6366f1','#22c55e','#eab308','#ef4444','#3b82f6','#f97316','#a855f7','#14b8a6','#f43f5e','#8b5cf6'] }]
  },
  options: { ...chartDefaults }
});
new Chart(document.getElementById('compChart'), {
  type: 'doughnut',
  data: {
    labels: ['Code', 'Comments', 'Blank'],
    datasets: [{ data: [{{ total_code_lines }}, {{ total_comment_lines }}, {{ total_blank_lines }}], backgroundColor: ['#6366f1','#22c55e','#2d3142'] }]
  },
  options: { ...chartDefaults }
});
</script>
</body>
</html>"""

_SMELL_DESCRIPTIONS = {
    "long_function": "Functions exceeding 50 lines — consider breaking them up",
    "too_many_args": "Functions with more than 5 parameters",
    "deep_nesting": "Code indented 4+ levels for 3+ consecutive lines",
    "magic_number": "Bare numeric literals that should be named constants",
    "long_file": "Files exceeding 400 lines",
    "todo_fixme": "TODO/FIXME/HACK/XXX markers left in comments",
}


def _render_simple(template: str, ctx: dict) -> str:
    """Very simple template renderer for when jinja2 is unavailable."""
    import re

    # Remove jinja2 block tags
    result = re.sub(r'\{%.*?%\}', '', template, flags=re.DOTALL)

    # Replace {{ var }} with ctx values
    def replace_var(m):
        key = m.group(1).strip()
        val = ctx.get(key, "")
        if isinstance(val, (list, dict)):
            import json
            return json.dumps(val)
        return str(val)

    result = re.sub(r'\{\{\s*(\w+)\s*\}\}', replace_var, result)
    return result


def generate(result: ScanResult) -> str:
    q = result.quality

    ctx = {
        "scanned_path": result.scanned_path,
        "scanned_at": result.scanned_at,
        "duration_seconds": result.duration_seconds,
        "score": q.score if q else 0,
        "grade": q.grade if q else "?",
        "complexity_score": q.complexity_score if q else 0,
        "smell_score": q.smell_score if q else 0,
        "dup_score": q.duplication_score if q else 0,
        "total_files": result.total_files,
        "total_lines": f"{result.total_lines:,}",
        "total_code_lines": result.total_code_lines,
        "total_comment_lines": result.total_comment_lines,
        "total_blank_lines": result.total_blank_lines,
        "total_functions": f"{result.total_functions:,}",
        "total_classes": f"{result.total_classes:,}",
        "total_smells": result.total_smells,
        "duplication": result.duplication is not None,
        "dup_pairs": result.duplication.duplicate_pairs if result.duplication else 0,
        "dup_lines": result.duplication.duplicated_lines if result.duplication else 0,
        "dup_pct": result.duplication.duplication_percent if result.duplication else 0,
        "dup_pair_rows": [
            {
                "file_a": p.file_a,
                "lines_a": f"{p.lines_a[0]}–{p.lines_a[1]}",
                "file_b": p.file_b,
                "lines_b": f"{p.lines_b[0]}–{p.lines_b[1]}",
                "sim": f"{p.similarity:.0%}",
            }
            for p in (result.duplication.pairs[:20] if result.duplication else [])
        ],
        "hotspot_rows": sorted(
            [
                {"path": f.path, "name": h.name, "complexity": h.complexity, "line": h.line}
                for f in result.files
                if f.complexity
                for h in f.complexity.hotspots
            ],
            key=lambda x: -x["complexity"],
        )[:20],
        "smell_summary": [
            {"type": t, "count": c, "desc": _SMELL_DESCRIPTIONS.get(t, "")}
            for t, c in sorted(result.smells_by_type.items(), key=lambda x: -x[1])
        ],
        "file_rows": sorted(
            [
                {
                    "path": f.path,
                    "language": f.language,
                    "lines": f.lines,
                    "code_lines": f.code_lines,
                    "comment_lines": f.comment_lines,
                    "functions": f.functions,
                    "classes": f.classes,
                    "smell_count": len(f.smells),
                }
                for f in result.files
            ],
            key=lambda x: -x["code_lines"],
        ),
        "lang_labels": list(result.languages.keys()),
        "lang_values": [v["code_lines"] for v in result.languages.values()],
    }

    try:
        from jinja2 import Environment
        env = Environment(autoescape=True)
        env.filters["tojson"] = __import__("json").dumps
        tmpl = env.from_string(_TEMPLATE)
        return tmpl.render(**ctx)
    except ImportError:
        return _render_simple(_TEMPLATE, ctx)


def write(result: ScanResult, output_path: str) -> None:
    Path(output_path).write_text(generate(result), encoding="utf-8")
