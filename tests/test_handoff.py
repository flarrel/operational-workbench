from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ops.data import FIRST, LAST, evidence, generate, snapshot
from ops.handoff import render_report, workflow


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "ops.sqlite"
        generate(path)
        self.dataset = snapshot(path, "Semua", FIRST, LAST)

    def test_escalation_links_sensor_evidence_and_tracks_review(self):
        item = workflow(self.dataset)
        sensor = next(row for row in self.dataset["signals"] if row["kind"] == "sensor_exception")
        sensor_id = f"S{sensor['id']}"
        self.assertIn(sensor_id, evidence(self.dataset))
        self.assertIn(sensor_id, item["escalation"]["message"])
        self.assertIn("belum dikirim", item["escalation"]["status"])
        self.assertIn("belum terkonfirmasi", item["escalation"]["message"])
        self.assertIn("Lewat tenggat", item["programs"][0]["status"])
        self.assertEqual(len(item["requests"]), 3)

    def test_no_signal_does_not_create_an_escalation_case(self):
        item = workflow({**self.dataset, "signals": [], "quality": []})
        self.assertIn("Belum ada kasus", item["escalation"]["status"])
        self.assertIn("Belum ada sinyal", item["escalation"]["message"])

    def test_status_and_briefing_share_analytics_and_handle_missing_evaluation(self):
        dashboard_total = self.dataset["totals"]["sales"]
        status = render_report(self.dataset, None, briefing=False)
        self.assertIn(str(dashboard_total), status)
        self.assertIn("data sintetis dan contoh penugasan", status)
        self.assertIn("Hasil evaluasi prompt belum tersedia.", status)
        report = {"summary": {"baseline": {"passed": 1, "total": 3}, "refined": {"passed": 2, "total": 3}}}
        briefing = render_report(self.dataset, report, briefing=True)
        self.assertIn(str(dashboard_total), briefing)
        self.assertIn("Persiapan tinjauan mingguan", briefing)
        self.assertIn("<td>Prompt revisi</td><td>2</td><td>3</td>", briefing)

    def test_report_escapes_dynamic_values(self):
        status = render_report({**self.dataset, "site": "<script>"}, None, briefing=False)
        self.assertNotIn("<script>", status)
        self.assertIn("&lt;script&gt;", status)
