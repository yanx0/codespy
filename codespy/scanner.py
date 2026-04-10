"""Core scanner: recursive traversal and analysis orchestration."""

import fnmatch
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .languages import (
    detect_language,
    is_text_language,
    DEFAULT_IGNORE_DIRS,
    DEFAULT_IGNORE_EXTENSIONS,
    DEFAULT_IGNORE_FILENAMES,
)
from .metrics import count_lines, count_functions_classes
from .models import FileResult, ScanResult
from .analyzers import complexity as complexity_analyzer
from .analyzers import smells as smell_analyzer
from .analyzers import duplication as dup_analyzer
from . import quality


@dataclass
class ScanConfig:
    ignore_dirs: set[str] = None  # type: ignore[assignment]
    ignore_extensions: set[str] = None  # type: ignore[assignment]
    ignore_filenames: set[str] = None  # type: ignore[assignment]
    extra_ignores: list[str] = None  # type: ignore[assignment]
    exclude_globs: list[str] = None  # type: ignore[assignment]
    analyze_complexity: bool = True
    analyze_smells: bool = True
    analyze_duplication: bool = True
    min_dup_lines: int = 6
    dup_threshold: float = 0.85
    quiet: bool = False

    def __post_init__(self) -> None:
        if self.ignore_dirs is None:
            self.ignore_dirs = set(DEFAULT_IGNORE_DIRS)
        if self.ignore_extensions is None:
            self.ignore_extensions = set(DEFAULT_IGNORE_EXTENSIONS)
        if self.ignore_filenames is None:
            self.ignore_filenames = set(DEFAULT_IGNORE_FILENAMES)
        if self.extra_ignores is None:
            self.extra_ignores = []
        if self.exclude_globs is None:
            self.exclude_globs = []


def _should_ignore(path: Path, rel_path: Path, config: ScanConfig) -> bool:
    """Return True if this path should be skipped."""
    # Check each directory component against ignore_dirs and simple extra_ignores
    for part in path.parts:
        if part in config.ignore_dirs:
            return True
        for pattern in config.extra_ignores:
            if fnmatch.fnmatch(part, pattern):
                return True

    # Check full relative path against glob patterns (e.g. */target/*)
    rel_str = str(rel_path)
    for pattern in config.exclude_globs:
        if fnmatch.fnmatch(rel_str, pattern):
            return True
        # Also match against any path component for bare dir names
        for part in rel_path.parts:
            if fnmatch.fnmatch(part, pattern):
                return True

    # Check file name and extension
    if path.name in config.ignore_filenames:
        return True
    if path.suffix.lower() in config.ignore_extensions:
        return True

    return False


def _iter_files(root: Path, config: ScanConfig):
    """Yield all non-ignored files under root."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        if _should_ignore(path, rel, config):
            continue
        yield path


def scan(target: str, config: Optional[ScanConfig] = None) -> ScanResult:
    """Scan a directory (or single file) and return a ScanResult."""
    if config is None:
        config = ScanConfig()

    start = time.monotonic()
    root = Path(target).resolve()

    if root.is_file():
        file_paths = [root]
    else:
        file_paths = list(_iter_files(root, config))

    if not config.quiet:
        print(f"Scanning {len(file_paths)} files in {root}...")

    file_results: list[FileResult] = []
    source_map: dict[str, list[str]] = {}

    for path in file_paths:
        language = detect_language(str(path))
        if not is_text_language(language):
            continue

        code, comments, blanks, src_lines = count_lines(str(path), language)
        if code + comments + blanks == 0:
            continue  # empty or unreadable

        functions, classes = count_functions_classes(str(path), language, src_lines)

        rel_path = str(path.relative_to(root) if root.is_dir() else path)

        fr = FileResult(
            path=rel_path,
            language=language,
            lines=code + comments + blanks,
            code_lines=code,
            comment_lines=comments,
            blank_lines=blanks,
            functions=functions,
            classes=classes,
        )

        if config.analyze_complexity:
            fr.complexity = complexity_analyzer.analyze(str(path), language, src_lines)

        if config.analyze_smells:
            fr.smells = smell_analyzer.analyze(
                str(path), language, src_lines, fr.lines
            )

        source_map[rel_path] = src_lines
        file_results.append(fr)

    if not config.quiet:
        print(f"Analyzed {len(file_results)} source files.")

    result = ScanResult(
        scanned_path=str(root),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(time.monotonic() - start, 3),
        files=file_results,
    )

    if config.analyze_duplication and len(file_results) >= 2:
        rel_paths = [fr.path for fr in file_results]
        result.duplication = dup_analyzer.analyze(rel_paths, source_map)

    result.quality = quality.compute(result)

    if not config.quiet:
        _print_summary(result)

    return result


def _print_summary(result: ScanResult) -> None:
    """Print a structured, hierarchy-first scan summary."""
    q = result.quality
    if not q:
        return

    W = 52
    bar = "─" * W

    grade_color = {"A": "\033[32m", "B": "\033[32m", "C": "\033[33m",
                   "D": "\033[33m", "F": "\033[31m"}.get(q.grade, "")
    reset = "\033[0m"

    # Sub-score notes
    hotspot_count = sum(len(f.complexity.hotspots) for f in result.files if f.complexity)
    serious_smells = sum(1 for f in result.files for s in f.smells
                         if s.type not in ("todo_fixme",))
    dup_pct = result.duplication.duplication_percent if result.duplication else 0.0

    cc_note = (f"{hotspot_count} function{'s' if hotspot_count != 1 else ''} exceed CC ≥ 10"
               if hotspot_count else "no hotspots above threshold")
    smell_note = (f"{serious_smells} structural smell{'s' if serious_smells != 1 else ''} "
                  f"across {result.total_files} file{'s' if result.total_files != 1 else ''}"
                  if serious_smells else "no structural smells")
    dup_note = (f"{dup_pct:.0f}% of lines in shared patterns"
                if result.duplication else "not analysed")

    # Top risk file
    top_risk_line = ""
    dup_files: set[str] = set()
    if result.duplication:
        for p in result.duplication.pairs:
            dup_files.add(p.file_a)
            dup_files.add(p.file_b)

    best, best_score = None, -1
    for f in result.files:
        c_f = min((f.complexity.max_complexity / 20.0) if f.complexity else 0, 1.0)
        s_f = min(len(f.smells) / 10.0, 1.0)
        d_f = 1.0 if f.path in dup_files else 0.0
        z_f = min(f.code_lines / 400.0, 1.0)
        score = (0.40 * c_f + 0.35 * s_f + 0.15 * d_f + 0.10 * z_f) * 100
        if score > best_score:
            best_score, best = score, f

    if best:
        fname = best.path.split("/")[-1]
        risk_lbl = ("CRITICAL" if best_score >= 70 else "HIGH" if best_score >= 45
                    else "MEDIUM" if best_score >= 20 else "LOW")
        details = []
        if best.complexity and best.complexity.hotspots:
            h = best.complexity.hotspots[0]
            details.append(f"{h.name}  CC={h.complexity}")
        serious = [s for s in best.smells if s.type not in ("todo_fixme", "magic_number")][:2]
        for s in serious:
            details.append(s.type.replace("_", " "))
        top_risk_line = f"  {fname}  [{risk_lbl}]\n  " + " · ".join(details) if details else f"  {fname}  [{risk_lbl}]"

    print(f"\n{bar}")
    print(f"  CodeSpy  ·  {result.scanned_path}")
    print(bar)
    print(f"\n  {grade_color}Grade {q.grade}  ·  {q.score}/100{reset}\n")
    print(f"  {'COMPLEXITY':<14} {q.complexity_score:>3}/100   {cc_note}")
    print(f"  {'SMELLS':<14} {q.smell_score:>3}/100   {smell_note}")
    print(f"  {'DUPLICATION':<14} {q.duplication_score:>3}/100   {dup_note}")
    if top_risk_line:
        print(f"\n  Top risk:")
        print(f"{top_risk_line}")
    print(f"\n  Next:  codespy target {result.scanned_path}")
    print()
