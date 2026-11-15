"""Tests for the report builder. Run from the repo root: python3 -m unittest discover -s tests"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "electronic-shopping"
SCRIPT = SKILL / "scripts" / "build_report.py"
sys.path.insert(0, str(SCRIPT.parent))
import build_report  # noqa: E402


def example() -> dict:
    d = json.loads((SKILL / "assets" / "research.example.json").read_text(encoding="utf-8"))
    d.pop("_schema")
    d["request"]["pincode"] = "507001"
    return d


class InrTest(unittest.TestCase):
    def test_indian_grouping(self):
        self.assertEqual(build_report.inr(999), "₹999")
        self.assertEqual(build_report.inr(18999), "₹18,999")
        self.assertEqual(build_report.inr(123456), "₹1,23,456")
        self.assertEqual(build_report.inr(12345678), "₹1,23,45,678")


class ValidateTest(unittest.TestCase):
    def test_example_passes_once_schema_removed(self):
        self.assertEqual(build_report.validate(example()), [])

    def test_example_file_itself_is_refused(self):
        d = json.loads((SKILL / "assets" / "research.example.json").read_text(encoding="utf-8"))
        self.assertTrue(any("_schema" in e for e in build_report.validate(d)))

    def test_price_without_url_or_date_is_refused(self):
        d = example()
        d["picks"][0]["prices"][0]["url"] = ""
        d["picks"][0]["prices"][1]["checked_on"] = "yesterday"
        errs = build_report.validate(d)
        self.assertTrue(any("url missing" in e for e in errs))
        self.assertTrue(any("checked_on" in e for e in errs))

    def test_pick_without_drawback_or_source_is_refused(self):
        d = example()
        d["picks"][1]["drawbacks"] = []
        d["picks"][1]["sources"] = []
        errs = build_report.validate(d)
        self.assertTrue(any("drawbacks" in e for e in errs))
        self.assertTrue(any("source" in e for e in errs))

    def test_bad_pincode_and_category(self):
        d = example()
        d["request"]["pincode"] = "5070"
        d["request"]["category"] = "fridge"
        errs = build_report.validate(d)
        self.assertTrue(any("pincode" in e for e in errs))
        self.assertTrue(any("category" in e for e in errs))

    def test_over_budget_warns(self):
        d = example()
        for pr in d["picks"][0]["prices"]:
            pr["price"] = 25000
        self.assertTrue(any("above the budget" in w for w in build_report.warnings(d)))


class PincodeTest(unittest.TestCase):
    def test_no_pincode_is_allowed(self):
        d = example()
        d["request"]["pincode"] = ""
        d["picks"][0]["prices"][0]["delivery_pincode"] = "500081"
        d["picks"][1]["prices"][0]["delivery_pincode"] = "500081"
        self.assertEqual(build_report.validate(d), [])
        out = build_report.render_html(d, build_report.LABELS["en"])
        self.assertIn("to 500081", out)
        self.assertNotIn("not the buyer", out)
        self.assertNotIn("Pincode ", build_report.render_whatsapp(d, build_report.LABELS["en"]))

    def test_delivery_result_needs_a_pincode_somewhere(self):
        d = example()
        d["request"]["pincode"] = ""
        d["picks"][0]["prices"][0].pop("delivery_pincode", None)
        self.assertTrue(any("delivery_pincode" in e for e in build_report.validate(d)))

    def test_result_for_another_pincode_is_flagged(self):
        d = example()  # buyer 507001, store checked 000000
        out = build_report.render_html(d, build_report.LABELS["en"])
        self.assertIn("to 000000 · not the buyer", out)

    def test_bad_delivery_pincode(self):
        d = example()
        d["picks"][0]["prices"][0]["delivery_pincode"] = "Hyderabad"
        self.assertTrue(any("delivery_pincode must be" in e for e in build_report.validate(d)))


class OutputTest(unittest.TestCase):
    def test_writes_html_and_whatsapp(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "research.json"
            src.write_text(json.dumps(example(), ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPT), str(src)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            html = (Path(t) / "report.html").read_text(encoding="utf-8")
            wa = (Path(t) / "whatsapp.txt").read_text(encoding="utf-8")
            self.assertIn("₹18,999", html)
            self.assertIn("My advice", html)
            self.assertIn("https://example.com/amazon-placeholder", wa)
            self.assertIn("2026-01-01", wa)

    def test_html_escapes_text(self):
        d = example()
        d["advice"] = "<script>alert(1)</script>"
        out = build_report.render_html(d, build_report.LABELS["en"])
        self.assertNotIn("<script>alert(1)</script>", out)

    def test_whatsapp_button_carries_the_exact_message(self):
        import html as h, re, urllib.parse
        d = example()
        out = build_report.render_html(d, build_report.LABELS["en"])
        href = h.unescape(re.search(r'href="(https://wa\.me/\?text=[^"]+)"', out).group(1))
        sent = urllib.parse.unquote(href.split("text=", 1)[1])
        self.assertEqual(sent, build_report.render_whatsapp(d, build_report.LABELS["en"]))
        self.assertIn('id="copy-btn"', out)

    def test_message_json_cannot_close_the_script_tag(self):
        d = example()
        d["advice"] = "</script><b>x</b>"
        out = build_report.render_html(d, build_report.LABELS["en"])
        block = out.split('id="wa-msg">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("</", block)

    def test_english_labels(self):
        out = build_report.render_whatsapp(example(), build_report.LABELS["en"])
        self.assertIn("My pick", out)

    def test_invalid_research_exits_1(self):
        with tempfile.TemporaryDirectory() as t:
            d = copy.deepcopy(example())
            d["picks"] = []
            src = Path(t) / "research.json"
            src.write_text(json.dumps(d), encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPT), str(src)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertFalse((Path(t) / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
