"""Tests for metrics module."""

import os
import unittest
from pathlib import Path

# Ensure package is importable from project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from codespy.metrics import count_lines, count_functions_classes

FIXTURES = Path(__file__).parent / "fixtures"


class TestCountLines(unittest.TestCase):

    def test_simple_py(self):
        path = str(FIXTURES / "simple.py")
        code, comments, blanks, src = count_lines(path, "Python")
        self.assertGreater(code, 0)
        self.assertGreater(comments, 0)  # has docstrings counted via block
        self.assertGreater(blanks, 0)
        self.assertEqual(len(src), code + comments + blanks)

    def test_nonexistent_file(self):
        code, comments, blanks, src = count_lines("/no/such/file.py", "Python")
        self.assertEqual(code, 0)
        self.assertEqual(src, [])

    def test_complex_py(self):
        path = str(FIXTURES / "complex.py")
        code, comments, blanks, src = count_lines(path, "Python")
        self.assertGreater(code, 20)


class TestCountFunctionsClasses(unittest.TestCase):

    def test_simple_py_functions(self):
        path = str(FIXTURES / "simple.py")
        _, _, _, src = count_lines(path, "Python")
        funcs, classes = count_functions_classes(path, "Python", src)
        self.assertEqual(funcs, 4)  # greet, add, multiply, divide
        self.assertEqual(classes, 1)  # Calculator

    def test_complex_py(self):
        path = str(FIXTURES / "complex.py")
        _, _, _, src = count_lines(path, "Python")
        funcs, classes = count_functions_classes(path, "Python", src)
        self.assertGreaterEqual(funcs, 3)  # parse_token, simple_func, deeply_nested
        self.assertEqual(classes, 0)


if __name__ == "__main__":
    unittest.main()
