# CHANGELOG

## [1.1.0] — 2026-11-04

### Fixed
- **N/A 规则被误判为失败**：`run_checks` 只判断 `result is None`，而引用完整性检查返回 `(None, msg)` 元组，导致 N/A 规则进入分母并计为失败，系统性压低分数。现在 `result[0] is None` 也会跳过。
- **目录模式与 zip 模式分数不一致**：目录模式的 `root_prefix` 为空，使 `name` 与目录名一致性检查永远 N/A。现在目录模式用磁盘目录名作为包名，同一内容两种形态同分（新增契约测试 `test_dir_and_zip_agree`）。

### Changed
- 占位符残留（MNT004）从"直接判 0 分"改为"封顶 60 分"：真实回归显示草稿态但结构完整的包应落在 WARN 区间。

### Added
- `docs/rules.md` 规则手册，含每条规则的阈值与四条已知局限。
- 18 项单元测试（覆盖加载、评分、渲染、CLI 退出码）。

## [1.0.0] — 2026-11-04

### Added
- 初始版本：`.skill`(zip) / 目录 / 单文件三种输入的加载器。
- 20 条规则（触发力 / 结构 / 可执行 / 可维护），权重合计 100。
- 加权评分 + 红旗封顶 + 优先级修复清单。
- Markdown / HTML / JSON 三种报告出口。
- CLI：`check` / `rules`，退出码 0/1/2/3 供 CI 使用。
- GitHub Actions：Python 3.9 / 3.11 / 3.13 × Ubuntu / Windows。
