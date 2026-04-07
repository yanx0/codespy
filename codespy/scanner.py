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
        q = result.quality
        print(f"Quality score: {q.score}/100 (Grade {q.grade})")

    return result
