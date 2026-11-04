"""渲染层：Markdown / HTML / JSON 三种出口。

为什么三种都要：
- Markdown：进 PR 评论、进 Issue、贴到群里
- HTML：给不装 Python 的人看（单文件、零外部依赖）
- JSON：给 CI 和别的脚本吃
"""

from __future__ import annotations

import html
import json
from datetime import datetime

from .score import Report, priority_fixes

BAR = "█"
EMPTY = "░"


def _bar(pct: int, width: int = 20) -> str:
    filled = round(width * pct / 100)
    return BAR * filled + EMPTY * (width - filled)


def render_json(report: Report, pkg_meta: dict) -> str:
    return json.dumps(
        {
            "tool": "skilllens",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "package": pkg_meta,
            "score": report.score,
            "grade": report.grade,
            "verdict": report.verdict,
            "caps": report.caps,
            "dimensions": [
                {"code": d.code, "name": d.name, "earned": d.earned, "possible": d.possible, "percent": d.percent}
                for d in report.dimensions
            ],
            "issues": [i.as_dict() for i in report.issues],
        },
        ensure_ascii=False,
        indent=2,
    )


def render_markdown(report: Report, pkg_meta: dict) -> str:
    lines = [
        f"# 技能体检报告 · {pkg_meta.get('name') or pkg_meta.get('source', '')}",
        "",
        f"> skilllens · {datetime.now().strftime('%Y-%m-%d %H:%M')} · 输入 `{pkg_meta.get('source','')}`",
        "",
        f"## 结论：**{report.score} / 100 · {report.grade} 级 · {report.verdict}**",
        "",
        f"{report.grade_note}",
        "",
    ]
    if report.caps:
        lines += ["> ⚠️ 触发红旗封顶：" + "；".join(report.caps), ""]

    lines += ["## 四维得分", "", "| 维度 | 得分 | 进度 | 未通过 |", "|---|---|---|---|"]
    for d in report.dimensions:
        lines.append(f"| {d.name}（{d.code}） | {d.earned}/{d.possible} | `{_bar(d.percent)}` {d.percent}% | {', '.join(d.failed) or '—'} |")
    lines.append("")

    fixes = priority_fixes(report)
    if fixes:
        lines += ["## 先改这 5 条", ""]
        for n, issue in enumerate(fixes, 1):
            lines.append(f"{n}. **[{issue.rule}] {issue.title}** —— 证据：{issue.evidence}\n   → 怎么改：{issue.fix}")
        lines.append("")

    fails = [i for i in report.failures if i not in fixes]
    if fails:
        lines += ["## 其余待改项", ""]
        for issue in fails:
            lines.append(f"- [{issue.rule}] {issue.title}：{issue.evidence} → {issue.fix}")
        lines.append("")

    passed = [i for i in report.issues if i.passed]
    lines += ["## 通过的检查", ""]
    for issue in passed:
        lines.append(f"- ✅ [{issue.rule}] {issue.title}：{issue.evidence}")
    lines.append("")
    lines += ["---", "", "分数算法：每条规则有固定权重，按维度归一化；4 条红旗（密钥/无 frontmatter/占位符）会封顶总分。详见 `docs/rules.md`。", ""]
    return "\n".join(lines)


def render_html(report: Report, pkg_meta: dict) -> str:
    def esc(s) -> str:
        return html.escape(str(s))

    dim_rows = ""
    for d in report.dimensions:
        dim_rows += (
            f'<div class="dim"><div class="dim-head"><span>{esc(d.name)} <em>{d.code}</em></span>'
            f"<span>{d.earned}/{d.possible} · {d.percent}%</span></div>"
            f'<div class="track"><div class="fill" style="width:{d.percent}%"></div></div></div>'
        )

    issue_rows = ""
    for i in report.issues:
        cls = "ok" if i.passed else ("bad" if i.level == "error" else "warn")
        mark = "通过" if i.passed else ("必须修" if i.level == "error" else "建议修")
        issue_rows += (
            f'<tr class="{cls}"><td><code>{esc(i.rule)}</code></td><td>{esc(i.title)}</td>'
            f"<td>{esc(mark)}</td><td>{esc(i.evidence)}</td><td>{esc(i.fix) or '—'}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>技能体检报告 · {esc(pkg_meta.get('name') or '未命名')}</title>
<style>
:root{{--bg:#fbfaf7;--card:#fff;--ink:#1b1a17;--muted:#6b6862;--line:#e6e2d9;--ok:#2f7d45;--warn:#b06a00;--bad:#b3261e;--accent:#2f5d8a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
.wrap{{max-width:960px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:26px;margin:0 0 6px}} .sub{{color:var(--muted);font-size:13px}}
.hero{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px;margin:22px 0}}
.score{{font-size:46px;font-weight:700;letter-spacing:-1px}}
.grade{{display:inline-block;margin-left:10px;padding:3px 12px;border-radius:999px;background:#eef3ee;color:var(--ok);font-size:14px}}
.caps{{background:#fdf3e7;border-left:3px solid var(--warn);padding:10px 14px;margin-top:14px;font-size:14px}}
.dim{{margin:14px 0}} .dim-head{{display:flex;justify-content:space-between;font-size:14px;margin-bottom:5px}} .dim-head em{{color:var(--muted);font-style:normal;font-size:12px}}
.track{{height:8px;background:#efece5;border-radius:999px;overflow:hidden}} .fill{{height:100%;background:var(--accent);border-radius:999px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13.5px}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#f4f1ea;font-weight:600;font-size:12.5px;color:var(--muted)}}
tr.bad td:nth-child(3){{color:var(--bad);font-weight:600}} tr.warn td:nth-child(3){{color:var(--warn)}} tr.ok td:nth-child(3){{color:var(--ok)}}
code{{font:12.5px/1.5 ui-monospace,Consolas,monospace;background:#f2efe8;padding:1px 5px;border-radius:4px}}
h2{{font-size:17px;margin:30px 0 12px}}
.foot{{color:var(--muted);font-size:12px;margin-top:28px}}
</style></head><body><div class="wrap">
<h1>技能体检报告 · {esc(pkg_meta.get('name') or '未命名')}</h1>
<div class="sub">skilllens · 输入 <code>{esc(pkg_meta.get('source',''))}</code> · {datetime.now().strftime('%Y-%m-%d %H:%M')} · {esc(pkg_meta.get('files',''))} 个文件</div>
<div class="hero">
  <div><span class="score">{report.score}</span><span class="grade">{report.grade} 级 · {report.verdict}</span></div>
  <div class="sub" style="margin-top:6px">{esc(report.grade_note)}</div>
  {('<div class="caps">⚠️ 红旗封顶：' + esc('；'.join(report.caps)) + '</div>') if report.caps else ''}
  <div style="margin-top:18px">{dim_rows}</div>
</div>
<h2>检查明细（{len(report.issues)} 项）</h2>
<table><thead><tr><th>规则</th><th>检查项</th><th>判定</th><th>证据</th><th>怎么改</th></tr></thead>
<tbody>{issue_rows}</tbody></table>
<div class="foot">分数算法：固定权重 + 维度归一化 + 红旗封顶。规则清单见仓库 docs/rules.md。</div>
</div></body></html>"""
