"""JSON output reporter."""

import dataclasses
import json
from pathlib import Path
from ..models import ScanResult


def _to_dict(obj) -> object:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj


def generate(result: ScanResult) -> str:
    """Serialize ScanResult to a JSON string."""
    data = {
        "meta": {
            "tool": "codespy",
            "version": "0.1.0",
            "scanned_path": result.scanned_path,
            "scanned_at": result.scanned_at,
            "duration_seconds": result.duration_seconds,
        },
        "summary": {
            "total_files": result.total_files,
            "total_lines": result.total_lines,
            "total_code_lines": result.total_code_lines,
            "total_comment_lines": result.total_comment_lines,
            "total_blank_lines": result.total_blank_lines,
            "total_functions": result.total_functions,
            "total_classes": result.total_classes,
            "languages": result.languages,
            "quality_score": result.quality.score if result.quality else None,
            "quality_grade": result.quality.grade if result.quality else None,
            "quality_breakdown": {
                "complexity_score": result.quality.complexity_score,
                "smell_score": result.quality.smell_score,
                "duplication_score": result.quality.duplication_score,
            } if result.quality else None,
        },
        "files": [
            {
                "path": f.path,
                "language": f.language,
                "lines": f.lines,
                "code_lines": f.code_lines,
                "comment_lines": f.comment_lines,
                "blank_lines": f.blank_lines,
                "functions": f.functions,
                "classes": f.classes,
                "complexity": {
                    "average": f.complexity.average,
                    "max": f.complexity.max_complexity,
                    "hotspots": [
                        {"name": h.name, "complexity": h.complexity, "line": h.line}
                        for h in f.complexity.hotspots
                    ],
                } if f.complexity else None,
                "smells": [
                    {"type": s.type, "name": s.name, "line": s.line, "detail": s.detail}
                    for s in f.smells
                ],
            }
            for f in result.files
        ],
        "duplication": {
            "duplicate_pairs": result.duplication.duplicate_pairs,
            "duplicated_lines": result.duplication.duplicated_lines,
            "duplication_percent": result.duplication.duplication_percent,
            "pairs": [
                {
                    "file_a": p.file_a,
                    "file_b": p.file_b,
                    "lines_a": p.lines_a,
                    "lines_b": p.lines_b,
                    "similarity": p.similarity,
                }
                for p in result.duplication.pairs
            ],
        } if result.duplication else None,
        "smells_summary": {
            "total": result.total_smells,
            "by_type": result.smells_by_type,
        },
    }
    return json.dumps(data, indent=2)


def write(result: ScanResult, output_path: str) -> None:
    Path(output_path).write_text(generate(result), encoding="utf-8")
