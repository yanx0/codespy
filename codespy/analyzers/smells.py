"""Code smell detection."""

import ast
import re
from ..models import SmellResult
from ..languages import AST_LANGUAGES

# Thresholds
LONG_FUNCTION_LINES = 50
TOO_MANY_ARGS = 5
DEEP_NESTING_DEPTH = 4
DEEP_NESTING_SUSTAINED = 3
LONG_FILE_LINES = 400
MAGIC_NUMBER_PATTERN = re.compile(
    r'(?<!["\'\w.])(?<!#)(?<!\d)(-?\d+(?:\.\d+)?)(?!\d)(?!["\'\w%])'
)
MAGIC_NUMBER_EXCLUDE = {0, 1, -1, 2, 100, 1000}
TODO_PATTERN = re.compile(r'\b(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)


class _SmellVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.smells: list[SmellResult] = []

    def _func_length(self, node: ast.FunctionDef) -> int:
        if not node.body:
            return 0
        start = node.lineno
        end = max(
            getattr(child, "end_lineno", node.lineno)
            for child in ast.walk(node)
            if hasattr(child, "end_lineno")
        )
        return end - start + 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        length = self._func_length(node)
        if length > LONG_FUNCTION_LINES:
            self.smells.append(SmellResult(
                type="long_function",
                name=node.name,
                line=node.lineno,
                detail=f"{length} lines",
            ))

        # Count args (exclude self, cls)
        args = node.args
        total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
        # Subtract self/cls
        first_arg_names = {a.arg for a in args.args[:1]}
        if first_arg_names & {"self", "cls"}:
            total_args -= 1
        if total_args > TOO_MANY_ARGS:
            self.smells.append(SmellResult(
                type="too_many_args",
                name=node.name,
                line=node.lineno,
                detail=f"{total_args} parameters",
            ))

        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]


def _detect_python_smells(source: str) -> list[SmellResult]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _SmellVisitor()
    visitor.visit(tree)
    return visitor.smells


def _detect_deep_nesting(lines: list[str], language: str) -> list[SmellResult]:
    """Detect sustained deep indentation."""
    smells: list[SmellResult] = []
    # Determine indent unit (spaces or tabs)
    indent_char = "\t" if any(l.startswith("\t") for l in lines) else " "
    unit = 4 if indent_char == " " else 1

    sustained = 0
    start_line = 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(indent_char))
        depth = indent // unit
        if depth >= DEEP_NESTING_DEPTH:
            if sustained == 0:
                start_line = i + 1
            sustained += 1
            if sustained == DEEP_NESTING_SUSTAINED:
                smells.append(SmellResult(
                    type="deep_nesting",
                    name="",
                    line=start_line,
                    detail=f"depth {depth}+ sustained for {DEEP_NESTING_SUSTAINED}+ lines",
                ))
        else:
            sustained = 0

    return smells


def _detect_magic_numbers(lines: list[str], language: str) -> list[SmellResult]:
    smells: list[SmellResult] = []
    comment_prefixes = ["#", "//", "*"]

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip comments, imports, constant assignments
        if any(stripped.startswith(p) for p in comment_prefixes):
            continue
        if re.match(r'^\s*(?:import|from|#|//|\*|const\s+\w+\s*=\s*\d)', line):
            continue
        # Skip lines that look like constant definitions
        if re.match(r'^\s*[A-Z_]{2,}\s*[=:]', line):
            continue

        for match in MAGIC_NUMBER_PATTERN.finditer(stripped):
            try:
                val = float(match.group(1))
            except ValueError:
                continue
            if val not in MAGIC_NUMBER_EXCLUDE:
                smells.append(SmellResult(
                    type="magic_number",
                    name="",
                    line=i + 1,
                    detail=f"literal {match.group(1)}",
                ))
                break  # one per line is enough

    return smells


def _detect_todos(lines: list[str]) -> list[SmellResult]:
    smells: list[SmellResult] = []
    for i, line in enumerate(lines):
        m = TODO_PATTERN.search(line)
        if m:
            rest = line[m.end():].strip().lstrip(":").strip()
            smells.append(SmellResult(
                type="todo_fixme",
                name=m.group(1).upper(),
                line=i + 1,
                detail=rest[:80] if rest else "",
            ))
    return smells


def analyze(path: str, language: str, source_lines: list[str], total_lines: int) -> list[SmellResult]:
    """Detect code smells in a file."""
    smells: list[SmellResult] = []

    if total_lines > LONG_FILE_LINES:
        smells.append(SmellResult(
            type="long_file",
            name=path.split("/")[-1],
            line=1,
            detail=f"{total_lines} lines",
        ))

    if language in AST_LANGUAGES:
        source = "\n".join(source_lines)
        smells.extend(_detect_python_smells(source))
    # For non-Python, we skip function-level smell detection (no AST)

    smells.extend(_detect_deep_nesting(source_lines, language))
    smells.extend(_detect_magic_numbers(source_lines, language))
    smells.extend(_detect_todos(source_lines))

    return smells
