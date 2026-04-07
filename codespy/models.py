from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ComplexityHotspot:
    name: str
    complexity: int
    line: int


@dataclass
class ComplexityResult:
    average: float
    max_complexity: int
    hotspots: list[ComplexityHotspot] = field(default_factory=list)


@dataclass
class SmellResult:
    type: str
    name: str
    line: int
    detail: str


@dataclass
class DuplicatePair:
    file_a: str
    file_b: str
    lines_a: list[int]  # [start, end]
    lines_b: list[int]  # [start, end]
    similarity: float


@dataclass
class DuplicationResult:
    duplicate_pairs: int
    duplicated_lines: int
    duplication_percent: float
    pairs: list[DuplicatePair] = field(default_factory=list)


@dataclass
class QualityScore:
    score: int
    grade: str
    complexity_score: int
    smell_score: int
    duplication_score: int


@dataclass
class FileResult:
    path: str
    language: str
    lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    functions: int
    classes: int
    complexity: Optional[ComplexityResult] = None
    smells: list[SmellResult] = field(default_factory=list)


@dataclass
class ScanResult:
    scanned_path: str
    scanned_at: str
    duration_seconds: float
    files: list[FileResult] = field(default_factory=list)
    duplication: Optional[DuplicationResult] = None
    quality: Optional[QualityScore] = None

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_lines(self) -> int:
        return sum(f.lines for f in self.files)

    @property
    def total_code_lines(self) -> int:
        return sum(f.code_lines for f in self.files)

    @property
    def total_comment_lines(self) -> int:
        return sum(f.comment_lines for f in self.files)

    @property
    def total_blank_lines(self) -> int:
        return sum(f.blank_lines for f in self.files)

    @property
    def total_functions(self) -> int:
        return sum(f.functions for f in self.files)

    @property
    def total_classes(self) -> int:
        return sum(f.classes for f in self.files)

    @property
    def languages(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for f in self.files:
            lang = f.language
            if lang not in result:
                result[lang] = {"files": 0, "code_lines": 0}
            result[lang]["files"] += 1
            result[lang]["code_lines"] += f.code_lines
        return result

    @property
    def total_smells(self) -> int:
        return sum(len(f.smells) for f in self.files)

    @property
    def smells_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.files:
            for smell in f.smells:
                counts[smell.type] = counts.get(smell.type, 0) + 1
        return counts
