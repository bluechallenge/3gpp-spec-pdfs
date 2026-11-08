"""Offline tests for get_spec.py helpers. Run: python3 -m unittest discover -s tests"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import get_spec as g


class VersionCode(unittest.TestCase):
    def test_code(self):
        self.assertEqual(g.code("19.5.0"), "j50")
        self.assertEqual(g.code("18.0.0"), "i00")
        self.assertEqual(g.code("19.10.1"), "ja1")

    def test_rank_orders_letters_after_digits(self):
        self.assertGreater(g.rank("ja0"), g.rank("j90"))
        self.assertGreater(g.rank("j50"), g.rank("i99"))


class SnapshotFolder(unittest.TestCase):
    def test_quarters(self):
        f = g.snapshot_folder
        self.assertEqual(f(19, datetime.date(2026, 11, 8)), "Release 19 - Sep'26")
        self.assertEqual(f(19, datetime.date(2026, 12, 1)), "Release 19 - Dec'26")
        self.assertEqual(f(18, datetime.date(2027, 2, 1)), "Release 18 - Dec'26")


class CleanTitle(unittest.TestCase):
    def test_drops_boilerplate_prefix(self):
        t = "NR; Physical channels and modulation"
        self.assertEqual(g.clean_title(t), "Physical channels and modulation")

    def test_keeps_real_title_and_makes_it_file_safe(self):
        self.assertEqual(g.clean_title("System architecture for the 5G System (5GS)"),
                         "System architecture for the 5G System (5GS)")
        self.assertEqual(g.clean_title("AI/ML: study"), "AI-ML- study")


if __name__ == "__main__":
    unittest.main()
