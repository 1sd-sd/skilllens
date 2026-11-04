"""csv_insight —— 最小可用实现（标准库版）。

刻意不依赖 pandas：这个脚本的用途是证明技能"照着步骤能跑"，不是做 BI 产品。
用法：python scripts/csv_insight.py examples/sample_orders.csv "哪个渠道最好"
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict


def read_rows(path: str) -> tuple[list[str], list[dict]]:
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh)
                return list(reader.fieldnames or []), list(reader)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"编码未知：{path}")


def pick_amount_col(headers: list[str]) -> str | None:
    for h in headers:
        if any(k in h for k in ("金额", "amount", "gmv", "price", "销售额")):
            return h
    return None


def pick_dim_col(headers: list[str], question: str) -> str | None:
    for h in headers:
        if h in question:
            return h
    for h in headers:
        if any(k in h for k in ("渠道", "channel", "品类", "category", "来源", "source")):
            return h
    return None


def bar(value: float, vmax: float, width: int = 20) -> str:
    n = 0 if vmax <= 0 else round(width * value / vmax)
    return "█" * n


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("用法：python scripts/csv_insight.py <csv> <问题>")
        return 2
    path, question = argv[1], argv[2]
    try:
        headers, rows = read_rows(path)
    except FileNotFoundError:
        print(f"文件不存在：{path}")
        return 2

    if not rows:
        print("空表，无法分析")
        return 2

    amount = pick_amount_col(headers)
    dim = pick_dim_col(headers, question)
    if not amount or not dim:
        print(f"找不到金额列或维度列。表头：{headers}")
        return 2

    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        try:
            groups[str(r.get(dim, "")).strip()].append(float(str(r.get(amount, "0")).replace(",", "") or 0))
        except ValueError:
            continue

    stat = {k: (len(v), sum(v), sum(v) / len(v)) for k, v in groups.items()}
    ranked = sorted(stat.items(), key=lambda kv: -kv[1][1])
    vmax = max(s[1] for s in stat.values()) if stat else 0

    print("## 体检\n")
    print(f"- 行数 {len(rows)} / 列数 {len(headers)}")
    print(f"- 维度列：{dim}；金额列：{amount}")
    if len(rows) < 30:
        print("- ⚠️ 样本 < 30，结论仅供参考\n")

    print("## 指标\n")
    print(f"| {dim} | 订单数 | 总额 | 均值 |")
    print("|---|---|---|---|")
    for k, (n, total, avg) in ranked:
        print(f"| {k} | {n} | {total:.2f} | {avg:.2f} |")

    print("\n## 结论\n")
    top = ranked[0]
    print(f"1. {top[0]} 总额最高：{top[1][1]:.2f}（{top[1][0]} 单，均值 {top[1][2]:.2f}）。")
    if len(ranked) > 1:
        low = ranked[-1]
        print(f"2. {low[0]} 总额最低：{low[1][1]:.2f}，与首位差 {top[1][1] - low[1][1]:.2f}。")
    print(f"3. 总样本 {len(rows)} 行，覆盖 {len(stat)} 个 {dim} 取值。")

    print("\n## 图\n")
    print("```")
    for k, (_, total, _) in ranked:
        print(f"{k[:6]:<7}{bar(total, vmax)} {total:.0f}")
    print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
