"""Cyclomatic complexity analysis."""

import ast
import re
from ..models import ComplexityResult, ComplexityHotspot
from ..languages import AST_LANGUAGES, DECISION_KEYWORDS

COMPLEXITY_THRESHOLD = 10


class _ComplexityVisitor(ast.NodeVisitor):
    """AST visitor that computes per-function cyclomatic complexity."""

    def __init__(self) -> None:
        self.results: list[tuple[str, int, int]] = []  # (name, complexity, lineno)
        self._stack: list[int] = []

    def _enter(self) -> None:
        self._stack.append(1)  # base complexity = 1

    def _exit(self, name: str, lineno: int) -> None:
        if self._stack:
            score = self._stack.pop()
            self.results.append((name, score, lineno))

    def _bump(self) -> None:
        if self._stack:
            self._stack[-1] += 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit(node.name, node.lineno)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_If(self, node: ast.If) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._bump()
        self.generic_visit(node)

    visit_AsyncFor = visit_For  # type: ignore[assignment]

    def visit_While(self, node: ast.While) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each additional operand in and/or adds a branch
        self._bump()
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self._bump()
        self.generic_visit(node)

    def visit_match_case(self, node: ast.match_case) -> None:  # type: ignore[attr-defined]
        self._bump()
        self.generic_visit(node)


def _analyze_python(source: str) -> list[tuple[str, int, int]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _ComplexityVisitor()
    visitor.visit(tree)
    return visitor.results


def _analyze_generic(lines: list[str], language: str) -> list[tuple[str, int, int]]:
    """Rough per-file complexity using regex decision-point counting."""
    keywords = DECISION_KEYWORDS.get(language, [])
    if not keywords:
        return []

    # Build combined pattern
    pattern = re.compile(r'\b(?:' + '|'.join(keywords) + r')\b')

    # Approximate: treat entire file as one "function"
    complexity = 1
    for line in lines:
        if not line.strip().startswith(("//", "#", "*", "/*")):
            complexity += len(pattern.findall(line))

    # Return as single "module-level" entry
    return [("<module>", complexity, 1)]


def analyze(path: str, language: str, source_lines: list[str]) -> ComplexityResult:
    """Analyze cyclomatic complexity for a file."""
    source = "\n".join(source_lines)

    if language in AST_LANGUAGES:
        results = _analyze_python(source)
    else:
        results = _analyze_generic(source_lines, language)

    if not results:
        return ComplexityResult(average=1.0, max_complexity=1, hotspots=[])

    complexities = [c for _, c, _ in results]
    avg = sum(complexities) / len(complexities)
    max_c = max(complexities)

    hotspots = [
        ComplexityHotspot(name=name, complexity=c, line=line)
        for name, c, line in results
        if c >= COMPLEXITY_THRESHOLD
    ]
    hotspots.sort(key=lambda h: h.complexity, reverse=True)

    return ComplexityResult(
        average=round(avg, 2),
        max_complexity=max_c,
        hotspots=hotspots[:10],  # top 10
    )
