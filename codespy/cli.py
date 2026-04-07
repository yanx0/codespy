"""CLI entry point."""

import sys
from pathlib import Path

from .scanner import ScanConfig, scan
from .reporters import json_reporter, html_reporter, md_reporter


def _argparse_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="codespy",
        description="Analyze code quality of a directory or file.",
    )
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
                        help="Exclude files matching glob pattern, e.g. '*/target/*' (repeatable)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument("--version", action="version", version="codespy 0.1.0")

    args = parser.parse_args()
    _run(args)


def _run(args) -> None:
    target = args.path
    if not Path(target).exists():
        print(f"Error: path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    config = ScanConfig(
        analyze_complexity=not args.no_complexity,
        analyze_smells=not args.no_smells,
        analyze_duplication=not args.no_duplication,
        extra_ignores=list(args.ignore),
        exclude_globs=list(args.exclude),
        quiet=args.quiet,
    )

    result = scan(target, config)

    # Write JSON
    json_reporter.write(result, args.output_json)
    if not args.quiet:
        print(f"JSON report: {args.output_json}")

    # Write human-readable report
    ext_map = {"html": "html", "md": "md", "csv": "csv"}
    report_out = args.report_out or f"report.{ext_map[args.report]}"

    if args.report == "html":
        html_reporter.write(result, report_out)
    elif args.report == "md":
        md_reporter.write(result, report_out)
    elif args.report == "csv":
        _write_csv(result, report_out)

    if not args.quiet:
        print(f"Report ({args.report}): {report_out}")


def _write_csv(result, output_path: str) -> None:
    import csv
    from pathlib import Path

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


def main() -> None:
    try:
        import click
        _click_main()
    except ImportError:
        _argparse_main()


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
    @click.option("--exclude", multiple=True, help="Exclude files matching glob, e.g. '*/target/*' (repeatable)")
    @click.option("-q", "--quiet", is_flag=True, help="Suppress progress output")
    @click.version_option("0.1.0", prog_name="codespy")
    def cli(path, output_json, report, report_out, no_complexity,
            no_duplication, no_smells, ignore, exclude, quiet):
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
        _run(args)

    cli()


if __name__ == "__main__":
    main()
