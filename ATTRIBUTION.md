# ATTRIBUTION — 拿来说明

> 这个项目不是从零发明的。以下是"拿了什么 / 从哪拿 / 改了什么 / 为什么改"的完整账本。

## 1. 参考来源

| 来源 | 链接 | 我拿了什么 |
|---|---|---|
| Anthropic Agent Skills 规范 | https://docs.claude.com/en/docs/agents-and-tools/agent-skills | frontmatter 字段语义（`name`/`description` 是唯一的触发依据）、kebab-case 命名、description 长度上限 1024、SKILL.md ≤ 500 行的分层加载思路 |
| skill-creator（Anthropic 内置技能） | 本地技能库 | "description 要写清 what + when + 用户原话"这条经验；渐进式披露（metadata → body → references）的三层结构 |
| ESLint 的规则模型 | https://eslint.org/docs/latest/extend/custom-rules | `rule id + 固定权重 + 可解释证据 + fix 建议` 的输出形态；"规则宁可小、宁可多，不要写一条大规则"的设计观 |
| Ruff / golangci-lint 的退出码约定 | — | CLI 退出码用 0/1/2 区分通过/警告/失败，让 CI 可以直接用 |
| 我自己 C4 的 `challenge-submission-checker` | 本仓库外（同作者 C4 提交） | 空壳检测、垃圾文件检测、密钥泄露检测的实现经验；以及它踩过的坑（见下） |
| 《The Pragmatic Programmer》的 "broken windows" | — | 「占位符残留」这条规则的动机：交付物里的一个 TODO 会让人以为整个包都是草稿 |

## 2. 直接复用 vs 重写

| 部分 | 处理 | 原因 |
|---|---|---|
| frontmatter 解析 | 重写（标准库） | 原实现依赖 PyYAML，破坏"零依赖"承诺 |
| 规则权重分配 | 自定 | 公开资料没有权重，只能按"失败后的代价"自己定 |
| 20 条规则的具体阈值 | 部分自定 | 80 字符下限、30 字符 Output 下限是拿 6 个真实包回归后定的，不是拍的 |
| 报告版式 | 自定 | 参考了 ESLint stylish formatter 的"先结论后明细"顺序 |
| 封顶（cap）机制 | 自创 | 参考了信用评分的"一票否决"思路：密钥泄露时，其他项全对也没有意义 |

## 3. 明确没拿的东西

| 没拿 | 原因 |
|---|---|
| LLM 语义评审 | 会把工具变成"需要 API key 才能跑"，牺牲可复现性和离线能力。这个能力放到 C6 的 Web 版做可选层 |
| 完整的 YAML 解析器 | 只支持技能 frontmatter 用到的子集，避免引入依赖 |
| 别人的评分量表（如 1–5 分制） | 0–100 + 等级更利于横向比较和设阈值 |

## 4. 我改了什么（相对参考来源的差异）

1. **把"规范建议"变成"可判定规则"**：Anthropic 文档说"description 应该包含何时使用"，我把它拆成两条可机器判定的规则（触发语存在性 + 引号原话数量 ≥ 2）。
2. **加了 N/A 语义**：规范里没有这个概念，但工程上必须有——否则"没有引用文件"的包会因为"引用完整性"被扣分。
3. **加了红旗封顶**：参考信用评分的一票否决，解决"总分 85 但里面有一把 API key"的荒谬情况。

## 5. 对来源的反馈

在真实包回归中发现 `wechat-doc-mapper` 与 `skill-explainer` 都缺 Input/Output 段——这两个是 C4 阶段的示例技能。这不是它们的错：C4 的评分标准里没有强制 IO 段。skilllens 的规则比 C4 更严，说明"能通过 C4"和"能被稳定复用"是两件事。

---

本项目代码为原创实现（MIT），上述来源仅提供设计思想与方法论，未复制其代码。
