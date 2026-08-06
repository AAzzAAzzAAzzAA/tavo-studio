#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import tavo_093_full_catalog as catalog  # noqa: E402
import tavo_093_runner_core as core  # noqa: E402


class Tavo093FullCatalogTests(unittest.TestCase):
    def test_every_approved_a_to_j_row_has_an_independent_case(self) -> None:
        cases = catalog.build_cases()
        self.assertEqual(core.validate_catalog(cases), [])
        self.assertEqual(len(cases), 192)
        expected = {
            "A": 27,
            "B": 15,
            "C": 14,
            "D": 10,
            "E": 11,
            "F": 12,
            "G": 8,
            "H": 76,
            "I": 13,
            "J": 6,
        }
        self.assertEqual(
            {
                item: sum(item in case.matrix_items for case in cases)
                for item in core.MATRIX_ITEMS
            },
            expected,
        )

    def test_retained_prompt_and_cross_feature_matrices_are_not_collapsed(self) -> None:
        keys = {case.key for case in catalog.build_cases()}
        self.assertEqual(
            len([key for key in keys if key.startswith("D93-HPE")]),
            34,
        )
        self.assertEqual(
            len([key for key in keys if key.startswith("D93-HCF")]),
            35,
        )
        self.assertIn("D93-HPE34", keys)
        self.assertIn("D93-HCF35", keys)

    def test_manual_real_model_boundaries_cannot_be_misreported_as_zero_call_passes(self) -> None:
        by_key = {case.key: case for case in catalog.build_cases()}
        for key in ("D93-C14", "D93-D10", "D93-E11"):
            case = by_key[key]
            self.assertTrue(case.manual)
            self.assertTrue(case.requires_real_model)
            with self.assertRaisesRegex(RuntimeError, "cannot pass"):
                core.case_result_record(case, "passed", evidence_level="offline")
            blocked = core.case_result_record(case, "blocked", evidence_level="offline")
            self.assertEqual(blocked["realModelRequestsSent"], 0)
            self.assertFalse(blocked["realProviderCredentialsUsed"])
            self.assertFalse(blocked["countsTowardKpi"])


if __name__ == "__main__":
    unittest.main()
