# skilllens

> **输入**一个 `.skill` 包（或技能目录），**输出**一个 0–100 分 + 20 条检查明细 + "下一条该改什么"。
> 离线、零第三方依赖、结果可复现——适合放进 CI，也适合发给同事当评审意见。

```bash
python -m skilllens check examples/csv-insight
```

```
== csv-insight  →  90/100  A 级  PASS
   触发力   25/25   100%
   结构    20/20   100%
   可执行   25/30    83%
   可维护   20/25    80%
```

---

## 解决什么问题

Agent 技能（SKILL.md / `.skill` 包）有一个尴尬的现实：**写完了不等于能用。**

常见的四种"看起来能跑"：

| 症状 | 后果 |
|---|---|
| `description` 只有一句话"分析数据" | 模型永远判断不出什么时候该触发它 |
| 有步骤但没有输入格式 | 每次执行都要人再解释一遍，等于没写 |
| 引用了 `scripts/foo.py`，包里却没有这个文件 | 执行到一半才报错 |
| SKILL.md 里还留着 `TODO: 补上说话人分离` | 交付的是草稿，不是能力 |

这些都不是"能力问题"，是**工程问题**。工程问题应该由工具兜住，而不是靠人每次凭记忆检查。

skilllens 做的就是这件事：把"技能包好不好"拆成 20 条可判定的规则，给出分数、证据和修复动作。

**没有它之前**：靠回忆 check list，漏一项就要等别人用坏了才知道。
**有了它之后**：`python -m skilllens check xxx` 一行命令，60 秒内知道该改哪。

---

## 快速开始

```bash
git clone https://github.com/1sd-sd/skilllens.git
cd skilllens

# 不需要安装，不需要 pip install
python -m skilllens check examples/csv-insight

# 生成三份报告（md / html / json）到 reports/
python -m skilllens check examples/csv-insight --out reports

# 批量体检一个目录下的所有技能
python -m skilllens check /path/to/skills --out reports

# 看规则清单
python -m skilllens rules
```

要求：Python 3.9+，无第三方依赖。

### 安装成命令（可选）

```bash
pip install -e .
skilllens check examples/csv-insight
```

---

## 示例

输入（节选 `examples/csv-insight/SKILL.md`）：

```markdown
---
name: csv-insight
description: >
  把一个 CSV 变成"可以直接放进周报的结论"……适用于"这张表说明什么"
  "帮我看看这份数据"这类请求。输入：文件路径；输出：Markdown 结论卡。
---
## 输入
| 字段 | 必填 | 说明 |
| csv_path | 是 | 本地 CSV 路径 |
```

输出：

```
== csv-insight  →  90/100  A 级  PASS
```

再换成草稿态的包：

```
== draft-skill  →  50/100  D 级  FAIL
   [MNT004] 无占位符残留 —— SKILL.md 仍含占位符：TODO
   [STR003] 有 Input 与 Output 段 —— 缺少 Input 段
```

---

## 项目结构

```
skilllens/
├── skilllens/
│   ├── loader.py      # 加载 .skill(zip)/目录/单文件，解析 frontmatter
│   ├── rules.py       # 20 条规则（4 维 × 5 条），每条带证据与修复动作
│   ├── score.py       # 加权评分 + 红旗封顶 + 优先级排序
│   ├── render.py      # Markdown / HTML / JSON 三种出口
│   └── cli.py         # 命令行入口与退出码
├── examples/
│   ├── csv-insight/   # A 级样本（可直接跑）
│   ├── thin-skill/    # 低分样本
│   └── draft-skill/   # 草稿态样本（占位符 + 垃圾文件）
├── tests/             # 18 项自测（标准库 unittest）
├── docs/rules.md      # 规则手册（每条规则的判定与阈值）
└── .github/workflows/ # CI：3.9/3.11/3.13 × Ubuntu/Windows
```

---

## 技术栈

- Python 3.9+（只用标准库：`zipfile` / `re` / `argparse` / `dataclasses` / `html`）
- 测试：`unittest`（18 项），CI 用 GitHub Actions 三平台跑
- 无网络调用、不写被检查目录、不对输入做任何修改

---

## 评分算法（30 秒版）

1. 20 条规则，权重合计 100 分，分布在 4 个维度：触发力 25 / 结构 20 / 可执行 30 / 可维护 25。
2. 某条规则若 N/A（例如正文没引用任何文件），不计入分母，避免系统性扣分。
3. 三条红旗直接封顶：密钥泄露 → 45 分，无 frontmatter → 40 分，占位符残留 → 60 分。
4. 等级：A ≥ 90 可直接发布；B ≥ 75 能用但触发率会打折；C ≥ 60 结构在细节缺；D < 60 还只是想法。

完整规则见 [`docs/rules.md`](docs/rules.md)。

---

## AI 生成说明

本项目使用 AI 辅助开发，逐轮的 prompt、修正与人工判断记录在 [AI_LOG.md](./AI_LOG.md)。

## 借鉴来源

规则体系与实现思路的来源、以及"拿了什么/改了什么"的取舍，记录在 [ATTRIBUTION.md](./ATTRIBUTION.md)。

## License

MIT
