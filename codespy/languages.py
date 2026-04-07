"""Language detection and comment syntax mapping."""

# Map file extension → language name
EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".lua": "Lua",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".dart": "Dart",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".sql": "SQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".md": "Markdown",
    ".tf": "Terraform",
    ".vim": "Vim Script",
}


# Map language → (line_comment_prefixes, block_comment: (start, end) or None)
COMMENT_SYNTAX: dict[str, tuple[list[str], tuple[str, str] | None]] = {
    "Python":       (["#"], ('"""', '"""')),
    "JavaScript":   (["//"], ("/*", "*/")),
    "TypeScript":   (["//"], ("/*", "*/")),
    "Go":           (["//"], ("/*", "*/")),
    "Java":         (["//"], ("/*", "*/")),
    "Kotlin":       (["//"], ("/*", "*/")),
    "Rust":         (["//"], ("/*", "*/")),
    "C":            (["//"], ("/*", "*/")),
    "C++":          (["//"], ("/*", "*/")),
    "C#":           (["//"], ("/*", "*/")),
    "Ruby":         (["#"], ("=begin", "=end")),
    "PHP":          (["//", "#"], ("/*", "*/")),
    "Swift":        (["//"], ("/*", "*/")),
    "Scala":        (["//"], ("/*", "*/")),
    "R":            (["#"], None),
    "Shell":        (["#"], None),
    "Lua":          (["--"], ("--[[", "]]")),
    "Elixir":       (["#"], None),
    "Haskell":      (["--"], ("{-", "-}")),
    "OCaml":        ([], ("(*", "*)")),
    "Clojure":      ([";"], None),
    "Dart":         (["//"], ("/*", "*/")),
    "HTML":         ([], ("<!--", "-->")),
    "CSS":          ([], ("/*", "*/")),
    "SCSS":         (["//"], ("/*", "*/")),
    "SQL":          (["--"], ("/*", "*/")),
    "YAML":         (["#"], None),
    "TOML":         (["#"], None),
    "Markdown":     ([], ("<!--", "-->")),
    "Terraform":    (["#", "//"], ("/*", "*/")),
    "Vim Script":   (['"'], None),
}

# Languages where we can use ast for precise analysis
AST_LANGUAGES = {"Python"}

# Decision keywords for regex-based complexity (non-Python)
DECISION_KEYWORDS: dict[str, list[str]] = {
    "JavaScript": ["if", "else if", "for", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "TypeScript": ["if", "else if", "for", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "Go":         ["if", "for", "case", "&&", r"\|\|"],
    "Java":       ["if", "else if", "for", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "Kotlin":     ["if", "for", "while", "when", "catch", "&&", r"\|\|", r"\?"],
    "Rust":       ["if", "for", "while", "match", "&&", r"\|\|"],
    "C":          ["if", "else if", "for", "while", "case", "&&", r"\|\|", r"\?"],
    "C++":        ["if", "else if", "for", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "C#":         ["if", "else if", "for", "foreach", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "Ruby":       ["if", "elsif", "unless", "while", "until", "case", "rescue", "&&", r"\|\|"],
    "PHP":        ["if", "elseif", "for", "foreach", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "Swift":      ["if", "for", "while", "case", "catch", "&&", r"\|\|", r"\?"],
    "Scala":      ["if", "for", "while", "match", "case", "catch", "&&", r"\|\|"],
}


def detect_language(path: str) -> str:
    """Detect language from file extension."""
    from pathlib import Path
    suffix = Path(path).suffix.lower()
    # Check original case too (for .R)
    original_suffix = Path(path).suffix
    return EXTENSION_MAP.get(original_suffix) or EXTENSION_MAP.get(suffix, "Unknown")


def get_comment_syntax(language: str) -> tuple[list[str], tuple[str, str] | None]:
    """Return (line_prefixes, block_delimiters) for a language."""
    return COMMENT_SYNTAX.get(language, (["#"], None))


def is_text_language(language: str) -> bool:
    """Return True if we should try to analyze this file as text."""
    return language != "Unknown"


# Default ignore patterns
DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".eggs", "*.egg-info", ".DS_Store", ".idea", ".vscode", "coverage",
    "htmlcov", ".coverage", "site-packages",
}

DEFAULT_IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2",
    ".lock",  # package lock files
}

DEFAULT_IGNORE_FILENAMES = {
    "package-lock.json", "yarn.lock", "Pipfile.lock", "poetry.lock",
    "Cargo.lock", "go.sum",
}
