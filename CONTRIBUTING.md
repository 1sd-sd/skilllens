# 参与贡献

感谢你想改进 skilllens。这个项目刻意保持"小"——所以在提 PR 之前，请先确认改动能通过下面三道门。

## 三道门

1. **可判定**：新规则必须能在不联网、不接 LLM 的前提下给出确定结论。同一个包跑两次结果必须一致。
2. **可解释**：失败时必须能给出证据（哪一行、哪个文件），不能只说"质量不佳"。
3. **可修复**：每条规则必须附一条具体动作，不能是"请优化"。

## 开发流程

```bash
git clone https://github.com/<你的用户名>/skilllens.git
cd skilllens
git checkout -b feat/your-rule

# 跑测试（不装任何依赖）
python -m unittest discover -s tests -v

# 加规则后，用真实包做回归，别只跑自己造的 fixture
python -m skilllens check examples --out reports
python -m skilllens check /path/to/your/real/skills
```

## 加一条规则的步骤

1. 在 `skilllens/rules.py` 写检查函数，返回 `(passed, evidence)`；不适用时返回 `(None, reason)`。
2. 在 `RULES` 里登记：id、维度、权重、级别、标题、修复动作。
3. **总权重必须仍是 100**（`tests/test_skilllens.py::test_weights_sum_to_100` 会拦你）。加规则就要从同维度其他规则里挪分。
4. 在 `docs/rules.md` 补一行说明。
5. 在 `examples/` 里加一个能触发它的最小样本，并写一条测试。

## Commit 约定

```
feat: 新增 EXE006 检查"步骤里是否有可复制命令"
fix: 修复 zip 内嵌套目录导致 name 误判
docs: 补充 MNT004 的已知误报场景
test: 补 dir/zip 同分契约测试
```

## 不接受的 PR

- 引入第三方依赖（含 PyYAML、requests）——这个项目的卖点之一是 `clone 下来就能跑`。
- 需要 API key 才能工作的功能。
- 自动修改被检查的文件（体检器只读）。
- 只有规则没有修复动作。

## Issue 模板

提 bug 时请附：

```
skilllens 版本：
Python 版本：
输入（能复现的最小包，或 SKILL.md 片段）：
期望分数 / 实际分数：
期望行为：
```

## License

贡献即同意以 MIT 协议发布。
