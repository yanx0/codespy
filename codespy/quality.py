"""Quality scoring: 0-100 composite with letter grade."""

from .models import ScanResult, QualityScore


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _complexity_score(result: ScanResult) -> int:
    """Score based on average cyclomatic complexity across all functions."""
    files_with_complexity = [
        f for f in result.files if f.complexity is not None
    ]
    if not files_with_complexity:
        return 100

    all_avgs = [f.complexity.average for f in files_with_complexity]
    overall_avg = sum(all_avgs) / len(all_avgs)

    total_hotspots = sum(len(f.complexity.hotspots) for f in files_with_complexity)
    hotspot_penalty = min(total_hotspots * 3, 30)

    # avg complexity 1 = 100, avg 5 = 84, avg 10 = 64, avg 15 = 44
    base = max(0, 100 - int((overall_avg - 1) * 8))
    return max(0, min(100, base - hotspot_penalty))


def _smell_score(result: ScanResult) -> int:
    """Score based on smell density (smells per 100 lines of code)."""
    total_code = result.total_code_lines
    if total_code == 0:
        return 100

    # Exclude informational todo_fixme from heavy penalty
    weighted_smells = 0
    for f in result.files:
        for smell in f.smells:
            if smell.type == "todo_fixme":
                weighted_smells += 0.2
            else:
                weighted_smells += 1.0

    density = (weighted_smells / total_code) * 100
    # density 0 = 100, density 5 = 85, density 10 = 70, density 20 = 40
    score = max(0, 100 - int(density * 3))
    return min(100, score)


def _duplication_score(result: ScanResult) -> int:
    """Score based on duplication percentage."""
    if result.duplication is None:
        return 100

    dup_pct = result.duplication.duplication_percent
    # 0% = 100, 5% = 75, 10% = 50, 20% = 0
    score = max(0, 100 - int(dup_pct * 5))
    return min(100, score)


def compute(result: ScanResult) -> QualityScore:
    """Compute composite quality score."""
    c = _complexity_score(result)
    s = _smell_score(result)
    d = _duplication_score(result)

    # Weighted average: 40% complexity, 35% smells, 25% duplication
    composite = int(c * 0.40 + s * 0.35 + d * 0.25)

    return QualityScore(
        score=composite,
        grade=_grade(composite),
        complexity_score=c,
        smell_score=s,
        duplication_score=d,
    )
