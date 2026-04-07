"""Tests for complexity analyzer."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from codespy.metrics import count_lines
from codespy.analyzers.complexity import analyze, COMPLEXITY_THRESHOLD

FIXTURES = Path(__file__).parent / "fixtures"


class TestComplexity(unittest.TestCase):

    def test_simple_file_low_complexity(self):
        path = str(FIXTURES / "simple.py")
        _, _, _, src = count_lines(path, "Python")
        result = analyze(path, "Python", src)
        self.assertLess(result.average, COMPLEXITY_THRESHOLD)
        self.assertEqual(len(result.hotspots), 0)

    def test_complex_file_has_hotspot(self):
        path = str(FIXTURES / "complex.py")
        _, _, _, src = count_lines(path, "Python")
        result = analyze(path, "Python", src)
        # parse_token should be a hotspot
        hotspot_names = [h.name for h in result.hotspots]
        self.assertIn("parse_token", hotspot_names)

    def test_complex_file_higher_average(self):
        simple_path = str(FIXTURES / "simple.py")
        complex_path = str(FIXTURES / "complex.py")
        _, _, _, simple_src = count_lines(simple_path, "Python")
        _, _, _, complex_src = count_lines(complex_path, "Python")
        simple_result = analyze(simple_path, "Python", simple_src)
        complex_result = analyze(complex_path, "Python", complex_src)
        self.assertGreater(complex_result.max_complexity, simple_result.max_complexity)

    def test_empty_file(self):
        result = analyze("fake.py", "Python", [])
        self.assertEqual(result.average, 1.0)
        self.assertEqual(result.max_complexity, 1)


if __name__ == "__main__":
    unittest.main()
