from contextlib import closing
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ops.data import FIRST, LAST, SIGNAL_TRUTH, connect, evidence, generate, snapshot


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ops.sqlite"
        generate(self.path)

    def test_detects_seeded_signals_and_discloses_quality(self):
        dataset = snapshot(self.path, "Semua", FIRST, LAST)
        self.assertEqual(dataset["totals"]["days"], 252)
        self.assertEqual(
            {(site, day.isoformat(), kind) for site, day, kind in SIGNAL_TRUTH},
            {(row["site"], row["day"], row["kind"]) for row in dataset["signals"]},
        )
        self.assertEqual({row["issue"] for row in dataset["quality"]}, {"duplicate", "missing_sensor"})
        self.assertEqual(len(dataset["quality"]), 2)

    def test_filtered_totals_and_source_link(self):
        target = FIRST + timedelta(days=65)
        dataset = snapshot(self.path, "Barat", target, target)
        with closing(connect(self.path)) as db:
            row = db.execute("SELECT id, sales FROM raw_daily WHERE site = ? AND day = ?", ("Barat", str(target))).fetchone()
        self.assertEqual(dataset["totals"]["sales"], row["sales"])
        self.assertEqual(dataset["weekly"][0]["sales"], row["sales"])
        self.assertIn(f"S{row['id']}", evidence(dataset))
        self.assertEqual(len(dataset["signals"]), 1)

    def test_empty_window(self):
        item = snapshot(self.path, "Timur", LAST + timedelta(days=1), LAST + timedelta(days=1))
        self.assertEqual(item["totals"]["sales"], 0)
        self.assertEqual(item["weekly"], [])
        self.assertEqual(item["signals"], [])
