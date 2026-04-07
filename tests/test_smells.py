"""Tests for smell detection."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from codespy.metrics import count_lines
from codespy.analyzers.smells import analyze

FIXTURES = Path(__file__).parent / "fixtures"


class TestSmells(unittest.TestCase):

    def test_detects_too_many_args(self):
        path = str(FIXTURES / "complex.py")
        _, _, _, src = count_lines(path, "Python")
        smells = analyze(path, "Python", src, len(src))
        types = [s.type for s in smells]
        self.assertIn("too_many_args", types)
        # parse_token has 7 args
        too_many = [s for s in smells if s.type == "too_many_args"]
        self.assertTrue(any(s.name == "parse_token" for s in too_many))

    def test_detects_todo(self):
        path = str(FIXTURES / "complex.py")
        _, _, _, src = count_lines(path, "Python")
        smells = analyze(path, "Python", src, len(src))
        types = [s.type for s in smells]
        self.assertIn("todo_fixme", types)

    def test_simple_file_fewer_smells(self):
        path = str(FIXTURES / "simple.py")
        _, _, _, src = count_lines(path, "Python")
        smells = analyze(path, "Python", src, len(src))
        # simple.py should have very few or no serious smells
        serious = [s for s in smells if s.type not in ("todo_fixme", "magic_number")]
        self.assertEqual(len(serious), 0)

    def test_detects_deep_nesting(self):
        path = str(FIXTURES / "complex.py")
        _, _, _, src = count_lines(path, "Python")
        smells = analyze(path, "Python", src, len(src))
        types = [s.type for s in smells]
        self.assertIn("deep_nesting", types)


if __name__ == "__main__":
    unittest.main()
