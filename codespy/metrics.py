"""Line counting and function/class extraction."""

import ast
import re
from pathlib import Path

from .languages import get_comment_syntax, AST_LANGUAGES


def count_lines(path: str, language: str) -> tuple[int, int, int, list[str]]:
    """Return (code_lines, comment_lines, blank_lines, source_lines).

    Reads the file once; all analyzers downstream receive the source_lines list.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, 0, 0, []

    lines = text.splitlines()
    line_prefixes, block_delimiters = get_comment_syntax(language)

    code = 0
    comments = 0
    blanks = 0

    in_block = False
    block_end = None

    for line in lines:
        stripped = line.strip()

        if not stripped:
            blanks += 1
            continue

        # Block comment tracking
        if block_delimiters:
            bstart, bend = block_delimiters
            if in_block:
                comments += 1
                if bend in stripped:
                    in_block = False
                continue
            if stripped.startswith(bstart) and bend not in stripped[len(bstart):]:
                # Multi-line block comment starts here
                in_block = True
                comments += 1
                continue
            if stripped.startswith(bstart) and bend in stripped[len(bstart):]:
                # Single-line block comment
                comments += 1
                continue

        # Line comment check
        is_comment = False
        for prefix in line_prefixes:
            if stripped.startswith(prefix):
                is_comment = True
                break

        if is_comment:
            comments += 1
        else:
            code += 1

    return code, comments, blanks, lines


def count_functions_classes_python(source: str) -> tuple[int, int]:
    """Count functions and classes in Python source using ast."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, 0

    functions = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    classes = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    )
    return functions, classes


# Regex patterns for function/class detection in non-Python languages
_FUNC_PATTERNS: list[re.Pattern] = [
    # JS/TS: function foo(, const foo = (, foo = function(, foo = () =>
    re.compile(r'\bfunction\s+\w+\s*\('),
    re.compile(r'\b(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(.*\)\s*=>'),
    re.compile(r'\b(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?function\s*\('),
    # Go: func foo(
    re.compile(r'\bfunc\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+\s*\('),
    # Java/C#/Kotlin: access modifier + type + name(
    re.compile(r'\b(?:public|private|protected|internal|static|final|override|virtual|abstract)\b.*\w+\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?[{]'),
    # Ruby: def foo
    re.compile(r'^\s*def\s+\w+'),
    # PHP: function foo(
    re.compile(r'\bfunction\s+\w+\s*\('),
    # Rust: fn foo(
    re.compile(r'\bfn\s+\w+\s*[<(]'),
    # Swift: func foo(
    re.compile(r'\bfunc\s+\w+\s*[<(]'),
]

_CLASS_PATTERNS: list[re.Pattern] = [
    re.compile(r'\bclass\s+\w+'),
    re.compile(r'\binterface\s+\w+'),
    re.compile(r'\bstruct\s+\w+\s*[{(]'),
    re.compile(r'\benum\s+\w+\s*[{(]'),
    re.compile(r'\btype\s+\w+\s+(?:struct|interface)\b'),
    re.compile(r'\btrait\s+\w+'),
    re.compile(r'\bimpl\s+\w+'),
]


def count_functions_classes_generic(lines: list[str]) -> tuple[int, int]:
    """Count functions and classes using regex heuristics."""
    functions = 0
    classes = 0
    seen_func_lines: set[int] = set()
    seen_class_lines: set[int] = set()

    for i, line in enumerate(lines):
        for pat in _FUNC_PATTERNS:
            if pat.search(line) and i not in seen_func_lines:
                functions += 1
                seen_func_lines.add(i)
                break
        for pat in _CLASS_PATTERNS:
            if pat.search(line) and i not in seen_class_lines:
                classes += 1
                seen_class_lines.add(i)
                break

    return functions, classes


def count_functions_classes(path: str, language: str, source_lines: list[str]) -> tuple[int, int]:
    """Dispatch to AST or regex depending on language."""
    if language in AST_LANGUAGES:
        source = "\n".join(source_lines)
        return count_functions_classes_python(source)
    else:
        return count_functions_classes_generic(source_lines)
