import unittest

from ops.evaluation import CASES, score
from ops.prompts import messages


class PromptEvaluationTests(unittest.TestCase):
    def test_rejects_uncited_and_invented_figures(self):
        case = CASES[0]
        good = "- Penjualan mencapai 212 unit [A].\n- Stok akhir 314 unit [B]."
        self.assertTrue(all(score(case, good).values()))
        self.assertFalse(score(case, good.replace("[B]", "[C]"))["required_sources"])
        self.assertFalse(score(case, good + " Ditambah 51 unit.")["no_extra_figures"])

    def test_missing_cases_reject_unsupported_figures(self):
        case = CASES[3]
        self.assertTrue(all(score(case, "Data tidak tersedia.").values()))
        self.assertFalse(score(case, "Data tidak tersedia. Gunakan 278.")["stays_on_requested_information"])

    def test_prompt_versions_receive_same_brief_and_evidence(self):
        case = CASES[0]
        for version in ("baseline", "refined"):
            with self.subTest(version=version):
                conversation = messages(case.task, case.brief, case.facts, version)
                self.assertIn(case.brief, conversation[-1]["content"])
                self.assertIn(case.facts["A"], conversation[-1]["content"])
