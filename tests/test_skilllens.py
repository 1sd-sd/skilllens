"""skilllens 自测（标准库 unittest，无第三方依赖）。

跑法：python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skilllens.loader import load_package  # noqa: E402
from skilllens.render import render_html, render_json, render_markdown  # noqa: E402
from skilllens.rules import run_checks  # noqa: E402
from skilllens.score import score  # noqa: E402

EXAMPLES = ROOT / "examples"
GOOD = EXAMPLES / "csv-insight"
THIN = EXAMPLES / "thin-skill"
DRAFT = EXAMPLES / "draft-skill"


def analyze(target) -> tuple:
    pkg = load_package(target)
    report = score(run_checks(pkg))
    return pkg, report


def failed_rules(report) -> set[str]:
    return {i.rule for i in report.failures}


class TestLoading(unittest.TestCase):
    def test_missing_path(self):
        pkg, report = analyze("definitely/not/here")
        self.assertEqual(pkg.kind, "missing")
        self.assertIn("PKG000", failed_rules(report))

    def test_dir_and_zip_agree(self):
        _, dir_report = analyze(GOOD)
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "csv-insight.skill"
            with zipfile.ZipFile(zpath, "w") as z:
                for f in GOOD.rglob("*"):
                    if f.is_file():
                        z.write(f, f"csv-insight/{f.relative_to(GOOD).as_posix()}")
            zpkg, zip_report = analyze(zpath)
        self.assertEqual(zpkg.root_prefix, "csv-insight/")
        self.assertEqual(dir_report.score, zip_report.score)

    def test_single_md(self):
        pkg, _ = analyze(GOOD / "SKILL.md")
        self.assertEqual(pkg.kind, "file")
        self.assertEqual(pkg.frontmatter["name"], "csv-insight")

    def test_unsupported_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.docx"
            p.write_text("x")
            pkg = load_package(p)
        self.assertEqual(pkg.kind, "unknown")


class TestScoring(unittest.TestCase):
    def test_good_skill_gets_A(self):
        _, report = analyze(GOOD)
        self.assertGreaterEqual(report.score, 90, f"csv-insight 只拿到 {report.score}，失败项：{failed_rules(report)}")
        self.assertEqual(report.grade, "A")

    def test_good_skill_has_no_error_level_failures(self):
        _, report = analyze(GOOD)
        errors = [i.rule for i in report.failures if i.level == "error"]
        self.assertEqual(errors, [])

    def test_thin_skill_fails(self):
        _, report = analyze(THIN)
        self.assertLess(report.score, 60)
        self.assertIn(report.verdict, ("WARN", "FAIL"))

    def test_draft_detects_placeholder_and_junk(self):
        _, report = analyze(DRAFT)
        rules = failed_rules(report)
        self.assertIn("MNT004", rules)  # TODO 残留
        self.assertIn("MNT005", rules)  # ~$ 垃圾文件
        self.assertLessEqual(report.score, 60)  # 占位符封顶

    def test_secret_is_red_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "leaky"
            d.mkdir()
            # 运行时拼接，避免在仓库里留下任何形似真实密钥的字面量
            fake = "sk-" + "test" + "0123456789abcdef0123456789abcdef"
            (d / "SKILL.md").write_text(
                "---\nname: leaky\ndescription: " + "很长" * 60 + "\n---\n\n" + "## 工具\n\nKEY=" + fake + "\n",
                encoding="utf-8",
            )
            _, report = analyze(d)
        self.assertIn("MNT006", failed_rules(report))
        self.assertLessEqual(report.score, 45)

    def test_missing_reference_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "refbroken"
            d.mkdir()
            src = (GOOD / "SKILL.md").read_text(encoding="utf-8")
            (d / "SKILL.md").write_text(src, encoding="utf-8")
            shutil.copytree(GOOD / "references", d / "references")
            # 不复制 scripts/，但 SKILL.md 里引用了 scripts/csv_insight.py
            _, report = analyze(d)
        self.assertIn("EXE002", failed_rules(report))

    def test_name_must_match_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "wrong-name"
            d.mkdir()
            (d / "SKILL.md").write_text((GOOD / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
            pkg, report = analyze(d)
        self.assertEqual(pkg.frontmatter["name"], "csv-insight")
        self.assertIn("TRG002", failed_rules(report))

    def test_deterministic(self):
        a = render_json(analyze(GOOD)[1], {"source": "x"})
        b = render_json(analyze(GOOD)[1], {"source": "x"})
        ja, jb = json.loads(a), json.loads(b)
        for doc in (ja, jb):
            doc.pop("generated_at")
        self.assertEqual(ja, jb)

    def test_weights_sum_to_100(self):
        from skilllens.rules import RULES

        self.assertEqual(sum(r.weight for r in RULES), 100)


class TestRender(unittest.TestCase):
    def setUp(self):
        self.pkg, self.report = analyze(GOOD)
        self.meta = {"source": str(GOOD), "name": self.pkg.frontmatter.get("name"), "files": len(self.pkg.files)}

    def test_markdown(self):
        md = render_markdown(self.report, self.meta)
        self.assertIn("技能体检报告", md)
        self.assertIn(str(self.report.score), md)

    def test_html_self_contained(self):
        doc = render_html(self.report, self.meta)
        self.assertTrue(doc.startswith("<!DOCTYPE html>"))
        self.assertNotIn("<script src=", doc)  # 不依赖外部脚本
        self.assertIn("skilllens", doc)

    def test_json_fields(self):
        data = json.loads(render_json(self.report, self.meta))
        self.assertEqual(set(data) >= {"score", "grade", "dimensions", "issues"}, True)
        self.assertEqual(len(data["dimensions"]), 4)


class TestCli(unittest.TestCase):
    def test_cli_exit_code_pass(self):
        from skilllens.cli import main

        self.assertEqual(main(["check", str(GOOD), "--quiet"]), 0)

    def test_cli_out_dir(self):
        from skilllens.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            code = main(["check", str(GOOD), "--out", tmp, "--quiet"])
            files = sorted(p.suffix for p in Path(tmp).iterdir())
        self.assertEqual(code, 0)
        self.assertEqual(files, [".html", ".json", ".md"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
