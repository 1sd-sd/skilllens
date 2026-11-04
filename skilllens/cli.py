"""CLI：`python -m skilllens check <目标>`。

退出码约定（给 CI 用）：
  0 = PASS（A/B）  1 = WARN（C）  2 = FAIL（D）  3 = 参数或读取错误
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import load_package
from .render import render_html, render_json, render_markdown
from .rules import DIMENSIONS, LEVELS, RULES, run_checks
from .score import Report, priority_fixes, score

EXIT = {"PASS": 0, "WARN": 1, "FAIL": 2}


def _meta(pkg) -> dict:
    return {
        "source": pkg.source,
        "kind": pkg.kind,
        "name": pkg.frontmatter.get("name", ""),
        "files": len(pkg.files),
        "bytes": sum(f.size for f in pkg.files),
        "error": pkg.error,
    }


def check_one(target: str, outdir: Path | None, quiet: bool, prefix: str = "") -> tuple[Report, dict]:
    pkg = load_package(target)
    issues = run_checks(pkg)
    report = score(issues)
    meta = _meta(pkg)

    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        stem = prefix or Path(target).stem or "package"
        (outdir / f"{stem}.md").write_text(render_markdown(report, meta), encoding="utf-8")
        (outdir / f"{stem}.html").write_text(render_html(report, meta), encoding="utf-8")
        (outdir / f"{stem}.json").write_text(render_json(report, meta), encoding="utf-8")

    if not quiet:
        name = meta["name"] or Path(target).name
        print(f"\n== {name}  →  {report.score}/100  {report.grade} 级  {report.verdict}")
        if pkg.error:
            print(f"   ! {pkg.error}")
        for d in report.dimensions:
            print(f"   {d.name:<4} {d.earned:>3}/{d.possible:<3}  {d.percent:>3}%")
        for issue in priority_fixes(report, 3):
            print(f"   [{issue.rule}] {issue.title} —— {issue.evidence}")
    return report, meta


def cmd_check(args) -> int:
    targets: list[str] = []
    for t in args.targets:
        p = Path(t)
        if p.is_dir() and not (p / "SKILL.md").exists() and not args.single:
            subs = sorted(x for x in p.iterdir() if x.is_dir() or x.suffix == ".skill")
            if subs:
                targets.extend(str(x) for x in subs)
                continue
        targets.append(t)

    outdir = Path(args.out) if args.out else None
    worst, results = 0, []
    for t in targets:
        report, meta = check_one(t, outdir, args.quiet)
        results.append((meta, report))
        worst = max(worst, EXIT[report.verdict])

    if len(results) > 1:
        print(f"\n{'包':<40}{'分数':>6}{'等级':>6}  结论")
        print("-" * 66)
        for meta, report in sorted(results, key=lambda r: r[1].score):
            label = (meta["name"] or Path(meta["source"]).name)[:38]
            print(f"{label:<40}{report.score:>6}{report.grade:>6}  {report.verdict}")
    if outdir:
        print(f"\n报告已写入 {outdir}/（每个包一份 .md/.html/.json）")
    return worst


def cmd_rules(_args) -> int:
    print("权重总和 = 100 分，按维度归一化。\n")
    for code, (name, weight, desc) in DIMENSIONS.items():
        print(f"\n### {name}（{code}，{weight} 分）—— {desc}")
        for rule in RULES:
            if rule.dimension == code:
                print(f"  {rule.id:<8}{rule.weight:>3} 分  [{LEVELS[rule.level]}]  {rule.title}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skilllens", description="技能包体检器：输入 .skill/目录，输出分数+问题+修复建议")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="体检一个或多个技能包")
    p_check.add_argument("targets", nargs="+", help=".skill 文件 / 技能目录 / SKILL.md / 包含多个包的父目录")
    p_check.add_argument("--out", help="报告输出目录（生成 .md/.html/.json）")
    p_check.add_argument("--quiet", action="store_true", help="只输出汇总表")
    p_check.add_argument("--single", action="store_true", help="把目录当成单个包，不向下展开")
    p_check.set_defaults(func=cmd_check)

    p_rules = sub.add_parser("rules", help="列出全部规则与权重")
    p_rules.set_defaults(func=cmd_rules)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 3
    except Exception as exc:
        print(f"skilllens 出错：{exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
