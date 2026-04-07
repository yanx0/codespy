"""Tests for quality scoring."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from codespy.scanner import scan, ScanConfig

FIXTURES = Path(__file__).parent / "fixtures"


class TestQuality(unittest.TestCase):

    def test_quality_score_range(self):
        result = scan(str(FIXTURES), ScanConfig(quiet=True))
        q = result.quality
        self.assertIsNotNone(q)
        self.assertGreaterEqual(q.score, 0)
        self.assertLessEqual(q.score, 100)

    def test_quality_grade_valid(self):
        result = scan(str(FIXTURES), ScanConfig(quiet=True))
        self.assertIn(result.quality.grade, ["A", "B", "C", "D", "F"])

    def test_sub_scores_in_range(self):
        result = scan(str(FIXTURES), ScanConfig(quiet=True))
        q = result.quality
        for score in [q.complexity_score, q.smell_score, q.duplication_score]:
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_simple_file_better_score_than_complex(self):
        simple = scan(str(FIXTURES / "simple.py"), ScanConfig(quiet=True))
        complex_ = scan(str(FIXTURES / "complex.py"), ScanConfig(quiet=True))
        # simple file should have >= quality score than complex
        self.assertGreaterEqual(simple.quality.score, complex_.quality.score)


if __name__ == "__main__":
    unittest.main()
