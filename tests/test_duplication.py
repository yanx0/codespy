"""Tests for duplication detector."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from codespy.metrics import count_lines
from codespy.analyzers.duplication import analyze

FIXTURES = Path(__file__).parent / "fixtures"


class TestDuplication(unittest.TestCase):

    def _load(self, filename: str) -> tuple[str, list[str]]:
        path = str(FIXTURES / filename)
        _, _, _, src = count_lines(path, "Python")
        return filename, src

    def test_finds_duplicate_between_similar_files(self):
        name_a, src_a = self._load("duplicate_a.py")
        name_b, src_b = self._load("duplicate_b.py")
        result = analyze([name_a, name_b], {name_a: src_a, name_b: src_b})
        # The validation pattern is very similar between the two files
        self.assertGreater(result.duplicate_pairs, 0)
        self.assertGreater(result.duplicated_lines, 0)

    def test_no_duplication_simple_vs_complex(self):
        name_a, src_a = self._load("simple.py")
        name_b, src_b = self._load("complex.py")
        result = analyze([name_a, name_b], {name_a: src_a, name_b: src_b})
        # simple.py and complex.py have no meaningful duplication
        # (duplication_percent should be low, not necessarily zero due to tiny blocks)
        self.assertLess(result.duplication_percent, 20)

    def test_single_file_no_duplication(self):
        name, src = self._load("simple.py")
        result = analyze([name], {name: src})
        self.assertEqual(result.duplicate_pairs, 0)

    def test_duplication_percent_range(self):
        name_a, src_a = self._load("duplicate_a.py")
        name_b, src_b = self._load("duplicate_b.py")
        result = analyze([name_a, name_b], {name_a: src_a, name_b: src_b})
        self.assertGreaterEqual(result.duplication_percent, 0)
        self.assertLessEqual(result.duplication_percent, 100)


if __name__ == "__main__":
    unittest.main()
