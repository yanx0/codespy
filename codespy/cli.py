"""CLI entry point."""

import json
import sys
from pathlib import Path

from .scanner import ScanConfig, scan
from .reporters import json_reporter, html_reporter, md_reporter


# ---------------------------------------------------------------------------
# target subcommand — used by the refactor-loop command
# ---------------------------------------------------------------------------

def _top_target(result) -> dict | None:
    """Return the highest-priority refactoring target from a scan result."""
    from .reporters.html_reporter import _file_risk_score, _risk_label

    dup_files: set[str] = set()
    if result.duplication:
        for p in result.duplication.pairs:
            dup_files.add(p.file_a)
            dup_files.add(p.file_b)

    best = None
    best_score = -1

    for f in result.files:
        score = _file_risk_score(f, dup_files)
        if score <= best_score:
            continue

        # Require at least one meaningful signal
        has_hotspot = f.complexity and bool(f.complexity.hotspots)
        has_smells = len([s for s in f.smells if s.type not in ("todo_fixme",)]) >= 2
        if not (has_hotspot or has_smells):
            continue

        best_score = score
        best = f

    if best is None:
        # Fallback: any file with a hotspot
        for f in result.files:
            if f.complexity and f.complexity.hotspots:
                best = f
                best_score = _file_risk_score(f, dup_files)
                break

    if best is None:
        return None

    # Build the target record
    hotspot = None
    if best.complexity and best.complexity.hotspots:
        hotspot = best.complexity.hotspots[0]  # already sorted by complexity desc

    top_smells = [s for s in best.smells if s.type not in ("todo_fixme", "magic_number")][:3]

    return {
        "file": best.path,
        "language": best.language,
        "risk_score": best_score,
        "risk_label": _risk_label(best_score),
        "complexity_score": best.complexity.average if best.complexity else None,
        "function": hotspot.name if hotspot else None,
        "function_line": hotspot.line if hotspot else None,
        "function_cc": hotspot.complexity if hotspot else None,
        "top_smells": [
            {"type": s.type, "name": s.name, "line": s.line, "detail": s.detail}
            for s in top_smells
        ],
        "action": (
            f"Refactor `{hotspot.name}` — cyclomatic complexity {hotspot.complexity} "
            f"(target: below 10)"
            if hotspot else
            f"Address {len(top_smells)} structural smell(s) in this file"
        ),
        "success_signal": (
            f"Re-scan shows `{hotspot.name}` CC drops by ≥2 points or falls below 10"
            if hotspot else
            f"Re-scan shows smell count decreases"
        ),
    }


def _run_target(path: str, exclude: list[str], human: bool = False) -> None:
    """Scan and print the top refactoring target."""
    if not Path(path).exists():
        print(f"Error: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    config = ScanConfig(
        analyze_duplication=False,
        exclude_globs=exclude,
        quiet=True,
    )
    result = scan(path, config)
    target = _top_target(result)

    if target is None:
        if human:
            print("\n  No high-priority target found — code looks clean!\n")
        else:
            print(json.dumps({"error": "No high-priority target found — code looks clean!"}))
        return

    if human:
        _print_target_human(target)
    else:
        print(json.dumps(target, indent=2))


def _print_target_human(t: dict) -> None:
    """Print a target record in structured, human-readable format."""
    W = 48
    bar = "─" * W
    fname = t["file"].split("/")[-1]
    smells = t.get("top_smells", [])

    why_parts = [f"CC={t['function_cc']}"]
    for s in smells:
        if s["type"] != "todo_fixme":
            label = s["type"].replace("_", " ")
            detail = f" ({s['detail']})" if s.get("detail") else ""
            why_parts.append(f"{label}{detail}")
    why = "  ·  ".join(why_parts[:3])

    print(f"\n{bar}")
    print(f"  REFACTOR TARGET")
    print(bar)
    print(f"  File      {fname}  [{t['risk_label']}  ·  risk {t['risk_score']}]")
    if t.get("function"):
        print(f"  Function  {t['function']}  ·  line {t.get('function_line', '?')}")
    print(f"\n  Why       {why}")
    print(f"\n  Action    {t['action']}")
    print(f"\n  Signal    {t['success_signal']}")
    print(f"\n{bar}")
    print(f"  Run:  /refactor-loop {t['file'].rsplit('/', 1)[0] or '.'}  to apply with Claude")
    print(f"{bar}\n")


# ---------------------------------------------------------------------------
# scan subcommand (existing behaviour)
# ---------------------------------------------------------------------------

def _argparse_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="codespy",
        description="Analyze code quality of a directory or file.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- scan (default) ---
    scan_p = subparsers.add_parser("scan", help="Scan a directory and generate reports")
    _add_scan_args(scan_p)

    # --- target ---
    target_p = subparsers.add_parser(
        "target",
        help="Find the highest-priority refactoring target in a directory",
    )
    target_p.add_argument("path", help="Directory or file to scan")
    target_p.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                          help="Exclude files matching glob (repeatable)")
    target_p.add_argument("--human", action="store_true",
                          help="Human-readable output instead of JSON")

    args = parser.parse_args()

    if args.command == "target":
        _run_target(args.path, args.exclude, human=getattr(args, "human", False))
    else:
        # Default: treat positional as scan (backwards-compatible)
        if args.command is None:
            # Re-parse without subcommands for backwards compat
            _argparse_scan_compat()
        else:
            _run(args)


def _argparse_scan_compat() -> None:
    """Backwards-compatible argparse scan (no subcommand needed)."""
    import argparse

    parser = argparse.ArgumentParser(prog="codespy")
    _add_scan_args(parser)
    args = parser.parse_args()
    _run(args)


def _add_scan_args(parser) -> None:
    parser.add_argument("path", help="Directory or file to scan")
    parser.add_argument("--output-json", default="report.json", metavar="PATH",
                        help="JSON output path (default: report.json)")
    parser.add_argument("--report", choices=["html", "md", "csv"], default="html",
                        help="Human-readable report format (default: html)")
    parser.add_argument("--report-out", default=None, metavar="PATH",
                        help="Report output path (default: report.<ext>)")
    parser.add_argument("--no-complexity", action="store_true", help="Skip complexity analysis")
    parser.add_argument("--no-duplication", action="store_true", help="Skip duplication analysis")
    parser.add_argument("--no-smells", action="store_true", help="Skip smell detection")
    parser.add_argument("--ignore", nargs="*", default=[], metavar="PATTERN",
                        help="Extra dir names to ignore (legacy)")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="Exclude files matching glob (repeatable)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open HTML report in browser")
    parser.add_argument("--version", action="version", version="codespy 0.1.0")


def _run(args) -> None:
    target = args.path
    if not Path(target).exists():
        print(f"Error: path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    config = ScanConfig(
        analyze_complexity=not args.no_complexity,
        analyze_smells=not args.no_smells,
        analyze_duplication=not args.no_duplication,
        extra_ignores=list(args.ignore) if args.ignore else [],
        exclude_globs=list(args.exclude) if args.exclude else [],
        quiet=args.quiet,
    )

    result = scan(target, config)

    # Write reports
    json_reporter.write(result, args.output_json)

    ext_map = {"html": "html", "md": "md", "csv": "csv"}
    report_out = args.report_out or f"report.{ext_map[args.report]}"

    if args.report == "html":
        html_reporter.write(result, report_out)
    elif args.report == "md":
        md_reporter.write(result, report_out)
    elif args.report == "csv":
        _write_csv(result, report_out)

    if not args.quiet:
        W = 52
        bar = "─" * W
        abs_path = Path(report_out).resolve()
        json_path = Path(args.output_json).resolve()
        print(bar)
        if args.report == "html":
            print(f"  Report:  file://{abs_path}")
        else:
            print(f"  Report:  {report_out}")
        print(f"  JSON:    {json_path}")
        print(f"{bar}\n")
        if args.report == "html":
            no_open = getattr(args, "no_open", False)
            if not no_open:
                import webbrowser
                webbrowser.open(abs_path.as_uri())


def _write_csv(result, output_path: str) -> None:
    import csv

    rows = [
        ["path", "language", "lines", "code_lines", "comment_lines",
         "blank_lines", "functions", "classes", "avg_complexity", "smells"]
    ]
    for f in result.files:
        rows.append([
            f.path, f.language, f.lines, f.code_lines, f.comment_lines,
            f.blank_lines, f.functions, f.classes,
            f.complexity.average if f.complexity else "",
            len(f.smells),
        ])

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


# ---------------------------------------------------------------------------
# main — dispatches to click or argparse
# ---------------------------------------------------------------------------

def main() -> None:
    # Route to target/scan subcommands before click sees argv
    real_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if real_args and real_args[0] == "scan":
        # Strip "scan" keyword — treat remainder as plain scan invocation
        sys.argv = [sys.argv[0]] + sys.argv[2:]
    if real_args and real_args[0] == "target":
        # Remove "target" from argv and dispatch
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        import argparse
        parser = argparse.ArgumentParser(prog="codespy target")
        parser.add_argument("path", help="Directory or file to scan")
        parser.add_argument("--exclude", action="append", default=[], metavar="GLOB")
        parser.add_argument("--human", action="store_true")
        args = parser.parse_args()
        _run_target(args.path, args.exclude, human=args.human)
        return

    try:
        import click
        _click_main()
    except ImportError:
        _argparse_scan_compat()


def _click_main() -> None:
    import click

    @click.command()
    @click.argument("path")
    @click.option("--output-json", default="report.json", show_default=True,
                  help="JSON output path")
    @click.option("--report", type=click.Choice(["html", "md", "csv"]), default="html",
                  show_default=True, help="Report format")
    @click.option("--report-out", default=None, help="Report output path")
    @click.option("--no-complexity", is_flag=True, help="Skip complexity analysis")
    @click.option("--no-duplication", is_flag=True, help="Skip duplication analysis")
    @click.option("--no-smells", is_flag=True, help="Skip smell detection")
    @click.option("--ignore", multiple=True, help="Extra dir names to ignore (legacy)")
    @click.option("--exclude", multiple=True, help="Exclude files matching glob (repeatable)")
    @click.option("-q", "--quiet", is_flag=True, help="Suppress progress output")
    @click.option("--no-open", is_flag=True, help="Do not auto-open HTML report in browser")
    @click.version_option("0.1.0", prog_name="codespy")
    def cli(path, output_json, report, report_out, no_complexity,
            no_duplication, no_smells, ignore, exclude, quiet, no_open):
        """Analyze code quality of a directory or file."""
        class _Args:
            pass
        args = _Args()
        args.path = path
        args.output_json = output_json
        args.report = report
        args.report_out = report_out
        args.no_complexity = no_complexity
        args.no_duplication = no_duplication
        args.no_smells = no_smells
        args.ignore = list(ignore)
        args.exclude = list(exclude)
        args.quiet = quiet
        args.no_open = no_open
        _run(args)

    cli()


if __name__ == "__main__":
    main()
