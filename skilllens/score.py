"""评分层：把 20 条检查的通过/失败折算成 0–100 分 + 等级 + 红旗封顶。

刻意做成"权重和归一化"而不是简单累加：
- 某些规则可能是 N/A（例如正文没有引用任何文件，就不该因为"引用完整性"扣分）
- 分母只算实际参与判定的权重，避免 N/A 规则系统性压低分数
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import DIMENSIONS, Issue

GRADES = [(90, "A", "可以直接发布"), (75, "B", "能用，但触发率会打折"), (60, "C", "结构在，执行细节缺失"), (0, "D", "还不算一个技能，只是一个想法")]

RED_FLAG_CAPS = {
    "MNT006": (45, "明文密钥泄露：先修这个，其余优化都没有意义"),
    "TRG001": (40, "frontmatter 缺失：AI 永远不会触发它"),
    "MNT004": (60, "占位符残留：交付物还是草稿"),
}


@dataclass
class DimensionScore:
    code: str
    name: str
    earned: int = 0
    possible: int = 0
    failed: list[str] = field(default_factory=list)

    @property
    def percent(self) -> int:
        return round(100 * self.earned / self.possible) if self.possible else 100


@dataclass
class Report:
    score: int
    grade: str
    grade_note: str
    dimensions: list[DimensionScore]
    issues: list[Issue]
    caps: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return {"A": "PASS", "B": "PASS", "C": "WARN", "D": "FAIL"}[self.grade]

    @property
    def failures(self) -> list[Issue]:
        return [i for i in self.issues if not i.passed]


def score(issues: list[Issue]) -> Report:
    dims = {code: DimensionScore(code, meta[0]) for code, meta in DIMENSIONS.items()}
    for issue in issues:
        d = dims[issue.dimension]
        d.possible += issue.weight
        if issue.passed:
            d.earned += issue.weight
        else:
            d.failed.append(issue.rule)

    possible = sum(d.possible for d in dims.values())
    earned = sum(d.earned for d in dims.values())
    raw = round(100 * earned / possible) if possible else 0

    caps: list[str] = []
    final = raw
    for issue in issues:
        if not issue.passed and issue.rule in RED_FLAG_CAPS:
            cap, why = RED_FLAG_CAPS[issue.rule]
            if final > cap:
                final = cap
                caps.append(f"{issue.rule} → 封顶 {cap} 分（{why}）")

    for threshold, grade, note in GRADES:
        if final >= threshold:
            break
    return Report(score=final, grade=grade, grade_note=note, dimensions=list(dims.values()), issues=issues, caps=caps)


def priority_fixes(report: Report, limit: int = 5) -> list[Issue]:
    """按 (严重级别, 权重) 排序，给出最值得先改的几条。"""
    order = {"error": 0, "warn": 1, "info": 2}
    fails = [i for i in report.failures if i.level != "info"]
    fails.sort(key=lambda i: (order[i.level], -i.weight))
    return fails[:limit]
