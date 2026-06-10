from __future__ import annotations

import unittest

from cleaner_app.models import RiskLevel
from cleaner_app.rules import PUP_KEYWORDS, get_cleanable_rules, get_inspection_rules, get_rules
from cleaner_app.scanner import find_keyword


class RuleCatalogTests(unittest.TestCase):
    def test_catalog_contains_common_stubborn_software_families(self) -> None:
        rules_text = " ".join(
            f"{rule.title} {rule.vendor} {' '.join(rule.path_patterns)}"
            for rule in get_rules()
        ).lower()

        for expected in ("360", "tencent", "kingsoft", "baidu", "sogou", "2345", "kuaizip"):
            self.assertIn(expected, rules_text)

    def test_high_risk_inspection_rules_are_not_selectable(self) -> None:
        for rule in get_inspection_rules():
            self.assertEqual(rule.risk, RiskLevel.HIGH)
            self.assertFalse(rule.default_selected)
            self.assertFalse(rule.selectable)

    def test_cleanable_rules_have_paths(self) -> None:
        rules = get_cleanable_rules()
        self.assertGreater(len(rules), 5)
        self.assertTrue(all(rule.path_patterns for rule in rules))

    def test_keyword_detection_matches_known_pup_terms(self) -> None:
        self.assertIn("2345", PUP_KEYWORDS)
        self.assertEqual(find_keyword(r"C:\Program Files\2345SoftMgr\helper.exe"), "2345")
        self.assertEqual(find_keyword(r"C:\Program Files\360\360safe.exe"), "360")


if __name__ == "__main__":
    unittest.main()
